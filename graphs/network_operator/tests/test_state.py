"""
tests/test_state.py
-------------------
Unit tests for state schema, helper utilities, and Pydantic model validation.
"""

import pytest
from pydantic import ValidationError

from network_operator.state import (
    Hypothesis,
    PlanStep,
    StepResult,
    PlannerOutput,
    RCAOutput,
    initial_state,
    get_current_step,
    get_pending_steps,
    mark_step_done,
    mark_step_skipped,
    all_steps_resolved,
    format_plan_for_prompt,
    format_hypotheses_for_prompt,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_hypothesis():
    return Hypothesis(id="h1_mtu_mismatch", description="MTU mismatch on peering interface")


@pytest.fixture
def sample_step():
    return PlanStep(
        id="check_interface_errors",
        hypothesis_id="h1_mtu_mismatch",
        description="Check for giant frame drops on ge-0/0/2",
        target_host="core-router-1",
        tool_category="ssh",
        command_hint="show interfaces ge-0/0/2 detail",
        expected_result="Zero or very low giant frame drop counters",
        destructive=False,
    )


@pytest.fixture
def sample_state_with_steps(sample_hypothesis, sample_step):
    state = initial_state("BGP flapping every 4 minutes")
    state["hypotheses"] = [sample_hypothesis.model_dump()]
    state["plan_steps"] = [
        sample_step.model_dump(),
        PlanStep(
            id="check_cpu_utilisation",
            hypothesis_id="h2_cpu_spike",
            description="Check CPU utilisation during flap window",
            target_host="core-router-1",
            tool_category="ssh",
            command_hint="show processes cpu",
            expected_result="CPU below 80% during flap events",
            destructive=False,
        ).model_dump(),
    ]
    state["current_step_id"] = "check_interface_errors"
    return state


# ---------------------------------------------------------------------------
# Hypothesis model
# ---------------------------------------------------------------------------

class TestHypothesis:
    def test_valid_hypothesis(self, sample_hypothesis):
        assert sample_hypothesis.id == "h1_mtu_mismatch"
        assert sample_hypothesis.status == "pending"

    def test_id_normalised_to_lowercase(self):
        h = Hypothesis(id="H1_MTU_MISMATCH", description="test")
        assert h.id == "h1_mtu_mismatch"

    def test_id_with_spaces_raises(self):
        with pytest.raises(ValidationError, match="snake_case"):
            Hypothesis(id="h1 mtu mismatch", description="test")

    def test_all_valid_statuses(self):
        for status in ("pending", "confirmed", "rejected", "ambiguous"):
            h = Hypothesis(id="h1_test", description="test", status=status)
            assert h.status == status

    def test_invalid_status_raises(self):
        with pytest.raises(ValidationError):
            Hypothesis(id="h1_test", description="test", status="unknown")


# ---------------------------------------------------------------------------
# PlanStep model
# ---------------------------------------------------------------------------

class TestPlanStep:
    def test_valid_step(self, sample_step):
        assert sample_step.id == "check_interface_errors"
        assert sample_step.destructive is False
        assert sample_step.status == "pending"

    def test_destructive_defaults_false(self):
        step = PlanStep(
            id="check_bgp",
            hypothesis_id="h1",
            description="test",
            target_host="router-1",
            tool_category="ssh",
            command_hint="show bgp",
            expected_result="session up",
        )
        assert step.destructive is False

    def test_id_with_spaces_raises(self):
        with pytest.raises(ValidationError):
            PlanStep(
                id="check bgp timers",
                hypothesis_id="h1",
                description="test",
                target_host="router-1",
                tool_category="ssh",
                command_hint="show bgp",
                expected_result="up",
            )

    def test_valid_tool_categories(self):
        for cat in ("ssh", "shell", "file_read", "search", "code_exec"):
            step = PlanStep(
                id=f"step_{cat}",
                hypothesis_id="h1",
                description="test",
                target_host="local",
                tool_category=cat,
                command_hint="cmd",
                expected_result="ok",
            )
            assert step.tool_category == cat


# ---------------------------------------------------------------------------
# PlannerOutput model
# ---------------------------------------------------------------------------

class TestPlannerOutput:
    def test_execute_requires_current_step_id(self, sample_step, sample_hypothesis):
        with pytest.raises(ValidationError, match="current_step_id must be non-empty"):
            PlannerOutput(
                reasoning="Some reasoning here about what I decided.",
                next_action="execute",
                hypotheses=[sample_hypothesis],
                plan_steps=[sample_step],
                current_step_id="",  # empty — should fail
            )

    def test_synthesize_allows_empty_step_id(self, sample_hypothesis):
        output = PlannerOutput(
            reasoning="Root cause confirmed, moving to synthesis.",
            next_action="synthesize",
            hypotheses=[sample_hypothesis],
            plan_steps=[],
            current_step_id="",
        )
        assert output.next_action == "synthesize"

    def test_replan_triggered_defaults_false(self, sample_step, sample_hypothesis):
        output = PlannerOutput(
            reasoning="Reviewing findings and advancing to next step.",
            next_action="execute",
            hypotheses=[sample_hypothesis],
            plan_steps=[sample_step],
            current_step_id="check_interface_errors",
        )
        assert output.replan_triggered is False


# ---------------------------------------------------------------------------
# State helper utilities
# ---------------------------------------------------------------------------

class TestStateHelpers:
    def test_initial_state_has_required_keys(self):
        state = initial_state("test problem")
        required = [
            "problem_statement", "context_summary", "hypotheses",
            "plan_steps", "current_step_id", "replan_count",
            "next_action", "planner_reasoning", "messages",
            "step_results", "findings_summary", "rca",
            "proposed_solution", "confidence",
        ]
        for key in required:
            assert key in state, f"Missing key: {key}"

    def test_initial_state_problem_statement(self):
        state = initial_state("BGP flapping")
        assert state["problem_statement"] == "BGP flapping"
        assert state["replan_count"] == 0
        assert state["messages"] == []

    def test_get_current_step_found(self, sample_state_with_steps):
        step = get_current_step(sample_state_with_steps)
        assert step is not None
        assert step.id == "check_interface_errors"

    def test_get_current_step_not_found(self, sample_state_with_steps):
        sample_state_with_steps["current_step_id"] = "nonexistent_step"
        step = get_current_step(sample_state_with_steps)
        assert step is None

    def test_get_pending_steps(self, sample_state_with_steps):
        pending = get_pending_steps(sample_state_with_steps)
        assert len(pending) == 2

    def test_mark_step_done(self, sample_state_with_steps):
        updated = mark_step_done(sample_state_with_steps, "check_interface_errors")
        statuses = {s["id"]: s["status"] for s in updated}
        assert statuses["check_interface_errors"] == "done"
        assert statuses["check_cpu_utilisation"] == "pending"

    def test_mark_step_skipped(self, sample_state_with_steps):
        updated = mark_step_skipped(
            sample_state_with_steps, "check_interface_errors", reason="test"
        )
        step = next(s for s in updated if s["id"] == "check_interface_errors")
        assert step["status"] == "skipped"
        assert step["skip_reason"] == "test"

    def test_all_steps_resolved_false(self, sample_state_with_steps):
        assert all_steps_resolved(sample_state_with_steps) is False

    def test_all_steps_resolved_true(self, sample_state_with_steps):
        # Mark all steps done
        state = sample_state_with_steps.copy()
        state["plan_steps"] = [
            {**s, "status": "done"} for s in state["plan_steps"]
        ]
        assert all_steps_resolved(state) is True

    def test_format_plan_for_prompt_contains_step_ids(self, sample_state_with_steps):
        text = format_plan_for_prompt(sample_state_with_steps)
        assert "check_interface_errors" in text
        assert "check_cpu_utilisation" in text

    def test_format_hypotheses_shows_status_icons(self, sample_state_with_steps):
        # Confirm one hypothesis
        state = sample_state_with_steps.copy()
        state["hypotheses"] = [
            {**state["hypotheses"][0], "status": "confirmed"}
        ]
        text = format_hypotheses_for_prompt(state)
        assert "✓" in text


# ---------------------------------------------------------------------------
# RCAOutput validation
# ---------------------------------------------------------------------------

class TestRCAOutput:
    def test_valid_rca(self):
        rca = RCAOutput(
            executive_summary="BGP session flapped due to MTU mismatch.",
            steps_executed=[],
            hypotheses_evaluated=[],
            root_cause="MTU mismatch on ge-0/0/2: router 9000, ISP 1500.",
            confidence="high",
            confidence_reasoning="Two independent data points confirm MTU mismatch.",
            proposed_solution="Set ip tcp adjust-mss 1452 on peering interface.",
            remediation_steps=["Step 1", "Step 2"],
            gaps_and_open_questions=["ISP-side MTU not directly verified."],
            follow_up_investigations=["Add MTU monitoring alert."],
        )
        assert rca.confidence == "high"
        assert len(rca.gaps_and_open_questions) == 1

    def test_gaps_can_be_empty_list(self):
        """gaps_and_open_questions can be an empty list (synthesizer fills it in)."""
        rca = RCAOutput(
            executive_summary="Summary",
            steps_executed=[],
            hypotheses_evaluated=[],
            root_cause="Root cause",
            confidence="low",
            confidence_reasoning="Insufficient evidence.",
            gaps_and_open_questions=[],
        )
        assert rca.gaps_and_open_questions == []
