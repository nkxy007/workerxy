"""
tests/test_nodes.py  (async)
-----------------------------
Unit tests for all async node functions.

Key differences vs sync version:
  - All tests are async def and decorated with @pytest.mark.asyncio
  - Model mocks use AsyncMock for .ainvoke() — not MagicMock
  - interrupt() is still sync and tested with regular MagicMock patch
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from langchain_core.messages import AIMessage

from network_operator.config import NetworkOperatorConfig
from network_operator.nodes.compressor import make_compressor_node
from network_operator.nodes.executor import make_executor_node, should_call_tools
from network_operator.nodes.planner import make_planner_node
from network_operator.nodes.synthesizer import make_synthesizer_node
from network_operator.state import (
    AgentState,
    PlannerOutput,
    HypothesisSchema,
    PlanStepSchema,
    RCAOutput,
    HypothesisEvaluated,
    StepSummary,
    StepResultSchema,
    initial_state,
)


# ─────────────────────────────────────────────────────────────────────────────
# Planner node tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPlannerNode:
    def _valid_output(self, next_action="execute") -> PlannerOutput:
        return PlannerOutput(
            reasoning="Giant drops on ge-0/0/2 confirm MTU mismatch. H1 is the root cause. One more step to rule out H2.",
            next_action=next_action,
            hypotheses=[HypothesisSchema(id="H1", description="MTU mismatch", status="confirmed")],
            plan_steps=[
                PlanStepSchema(
                    id="check_cpu_detail",
                    hypothesis_id="H2",
                    description="Check CPU",
                    target_host="core-router-1",
                    tool_category="ssh",
                    command_hint="show cpu",
                    expected_result="CPU < 70%",
                )
            ] if next_action == "execute" else [],
            current_step_id="check_cpu_detail" if next_action == "execute" else "",
        )

    @pytest.mark.asyncio
    @patch("network_operator.nodes.planner.init_chat_model")
    async def test_planner_returns_state_patch(self, mock_init, test_cfg, blank_state):
        mock_model = MagicMock()
        # ainvoke must be AsyncMock so it can be awaited
        structured = MagicMock()
        structured.ainvoke = AsyncMock(return_value={
            "parsed": self._valid_output("execute"),
            "parsing_error": None,
        })
        mock_model.with_structured_output.return_value = structured
        mock_init.return_value = mock_model

        node = make_planner_node(cfg=test_cfg)
        result = await node(blank_state)

        assert "next_action" in result
        assert "planner_reasoning" in result
        assert result["next_action"] == "execute"

    @pytest.mark.asyncio
    @patch("network_operator.nodes.planner.init_chat_model")
    async def test_planner_routes_to_synthesize(self, mock_init, test_cfg, state_with_results):
        mock_model = MagicMock()
        structured = MagicMock()
        structured.ainvoke = AsyncMock(return_value={
            "parsed": self._valid_output("synthesize"),
            "parsing_error": None,
        })
        mock_model.with_structured_output.return_value = structured
        mock_init.return_value = mock_model

        node = make_planner_node(cfg=test_cfg)
        result = await node(state_with_results)

        assert result["next_action"] == "synthesize"

    @pytest.mark.asyncio
    @patch("network_operator.nodes.planner.init_chat_model")
    async def test_planner_retries_on_validation_failure(self, mock_init, test_cfg, blank_state):
        call_count = 0
        valid_output = self._valid_output()

        async def side_effect(messages):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return {"parsed": None, "parsing_error": "schema validation failed"}
            return {"parsed": valid_output, "parsing_error": None}

        mock_model = MagicMock()
        structured = MagicMock()
        structured.ainvoke = side_effect  # regular async function, not AsyncMock
        mock_model.with_structured_output.return_value = structured
        mock_init.return_value = mock_model

        node = make_planner_node(cfg=test_cfg)
        result = await node(blank_state)

        assert call_count == 3
        assert result["next_action"] == "execute"

    @pytest.mark.asyncio
    @patch("network_operator.nodes.planner.init_chat_model")
    async def test_planner_fails_safe_after_max_retries(self, mock_init, test_cfg, blank_state):
        mock_model = MagicMock()
        structured = MagicMock()
        structured.ainvoke = AsyncMock(return_value={
            "parsed": None,
            "parsing_error": "always fails",
        })
        mock_model.with_structured_output.return_value = structured
        mock_init.return_value = mock_model

        node = make_planner_node(cfg=test_cfg)
        result = await node(blank_state)

        assert result["next_action"] == "synthesize"
        assert "failed" in result["planner_reasoning"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# Executor node tests
# ─────────────────────────────────────────────────────────────────────────────

class TestExecutorNode:
    @pytest.mark.asyncio
    @patch("network_operator.nodes.executor.init_chat_model")
    async def test_executor_runs_step_and_records_result(
        self, mock_init, test_cfg, mock_tools, state_with_plan
    ):
        mock_base = MagicMock()
        # bind_tools model: ainvoke returns AIMessage with no tool_calls (step done)
        bound = MagicMock()
        bound.ainvoke = AsyncMock(return_value=AIMessage(content="Analysis complete."))
        mock_base.bind_tools.return_value = bound

        # result extractor: ainvoke returns StepResultSchema
        extractor = MagicMock()
        extractor.ainvoke = AsyncMock(return_value=StepResultSchema(
            step_id="check_interface_errors_ge002",
            status="confirmed",
            finding="Interface ge-0/0/2 shows 4,821 giant drops. MTU configured as 9000.",
        ))
        mock_base.with_structured_output.return_value = extractor
        mock_init.return_value = mock_base

        node = make_executor_node(tools=mock_tools, cfg=test_cfg)
        result = await node(state_with_plan)

        assert "step_results" in result
        assert result["step_results"][0]["step_id"] == "check_interface_errors_ge002"
        assert result["step_results"][0]["status"] == "confirmed"

    @pytest.mark.asyncio
    @patch("network_operator.nodes.executor.init_chat_model")
    async def test_executor_marks_step_done(self, mock_init, test_cfg, mock_tools, state_with_plan):
        mock_base = MagicMock()
        bound = MagicMock()
        bound.ainvoke = AsyncMock(return_value=AIMessage(content="done"))
        mock_base.bind_tools.return_value = bound
        extractor = MagicMock()
        extractor.ainvoke = AsyncMock(return_value=StepResultSchema(
            step_id="check_interface_errors_ge002",
            status="ambiguous",
            finding="Output was unexpected. Observed X but expected Y. Result unclear.",
        ))
        mock_base.with_structured_output.return_value = extractor
        mock_init.return_value = mock_base

        node = make_executor_node(tools=mock_tools, cfg=test_cfg)
        result = await node(state_with_plan)

        done = [s for s in result["plan_steps"] if s["id"] == "check_interface_errors_ge002"]
        assert done[0]["status"] == "done"

    @pytest.mark.asyncio
    @patch("network_operator.nodes.executor.interrupt")
    @patch("network_operator.nodes.executor.init_chat_model")
    async def test_executor_gates_destructive_step(
        self, mock_init, mock_interrupt, test_cfg, mock_tools, state_with_plan
    ):
        state = dict(state_with_plan)
        state["plan_steps"] = [
            {**state["plan_steps"][0], "destructive": True},
            state["plan_steps"][1],
        ]
        # interrupt() is SYNC — use regular return_value, not AsyncMock
        mock_interrupt.return_value = {"approved": False, "reason": "Not during maintenance window"}
        mock_init.return_value = MagicMock()

        node = make_executor_node(tools=mock_tools, cfg=test_cfg)
        result = await node(AgentState(**state))

        mock_interrupt.assert_called_once()
        skipped = [s for s in result["plan_steps"] if s["status"] == "skipped"]
        assert len(skipped) == 1
        assert "maintenance" in skipped[0]["skip_reason"].lower()

    @pytest.mark.asyncio
    @patch("network_operator.nodes.executor.interrupt")
    @patch("network_operator.nodes.executor.init_chat_model")
    async def test_executor_proceeds_when_destructive_approved(
        self, mock_init, mock_interrupt, test_cfg, mock_tools, state_with_plan
    ):
        state = dict(state_with_plan)
        state["plan_steps"] = [
            {**state["plan_steps"][0], "destructive": True},
            state["plan_steps"][1],
        ]
        mock_interrupt.return_value = {"approved": True}  # sync return

        mock_base = MagicMock()
        bound = MagicMock()
        bound.ainvoke = AsyncMock(return_value=AIMessage(content="done"))
        mock_base.bind_tools.return_value = bound
        extractor = MagicMock()
        extractor.ainvoke = AsyncMock(return_value=StepResultSchema(
            step_id="check_interface_errors_ge002",
            status="confirmed",
            finding="4821 giant drops. MTU is 9000. Expected zero giants for healthy state.",
        ))
        mock_base.with_structured_output.return_value = extractor
        mock_init.return_value = mock_base

        node = make_executor_node(tools=mock_tools, cfg=test_cfg)
        result = await node(AgentState(**state))

        done = [s for s in result["plan_steps"] if s["status"] == "done"]
        assert len(done) == 1

    @pytest.mark.asyncio
    @patch("network_operator.nodes.executor.init_chat_model")
    async def test_executor_tool_call_loop(self, mock_init, test_cfg, mock_tools, state_with_plan):
        """
        Executor should return updated messages when the model requests a tool call,
        allowing LangGraph to route to the ToolNode.
        """
        mock_base = MagicMock()
        bound = MagicMock()
        # First invocation returns a tool call request
        bound.ainvoke = AsyncMock(return_value=AIMessage(
            content="",
            tool_calls=[{
                "name": "net_run_commands_on_device",
                "args": {"device_management_ip": "core-router-1", "commands": ["show interfaces ge-0/0/2"]},
                "id": "tc1",
            }],
        ))
        mock_base.bind_tools.return_value = bound
        mock_init.return_value = mock_base

        node = make_executor_node(tools=mock_tools, cfg=test_cfg)
        result = await node(state_with_plan)

        # Should return messages with the tool call — graph routes to ToolNode next
        assert "messages" in result
        last_msg = result["messages"][-1]
        assert isinstance(last_msg, AIMessage)
        assert last_msg.tool_calls


# ─────────────────────────────────────────────────────────────────────────────
# should_call_tools  (sync edge function — tested normally)
# ─────────────────────────────────────────────────────────────────────────────

class TestShouldCallTools:
    def test_returns_tools_when_ai_has_tool_calls(self, blank_state):
        state = dict(blank_state)
        state["messages"] = [AIMessage(
            content="",
            tool_calls=[{"name": "net_run_commands_on_device", "args": {}, "id": "t1"}],
        )]
        assert should_call_tools(AgentState(**state)) == "tools"

    def test_returns_compressor_when_no_tool_calls(self, blank_state):
        state = dict(blank_state)
        state["messages"] = [AIMessage(content="All done.")]
        assert should_call_tools(AgentState(**state)) == "compressor"

    def test_returns_compressor_when_no_messages(self, blank_state):
        assert should_call_tools(blank_state) == "compressor"


# ─────────────────────────────────────────────────────────────────────────────
# Compressor node tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCompressorNode:
    @pytest.mark.asyncio
    @patch("network_operator.nodes.compressor.init_chat_model")
    async def test_compressor_produces_summary(self, mock_init, test_cfg, state_with_results):
        mock_model = MagicMock()
        # ainvoke must be AsyncMock
        mock_model.ainvoke = AsyncMock(return_value=MagicMock(
            content=(
                "## Hypotheses Status\n[H1] CONFIRMED\n\n"
                "## Steps Completed\n[check_interface_errors_ge002] CONFIRMED\n\n"
                "## Key Observations\n• Giant drops confirmed\n\n"
                "## Outstanding Questions\nNone"
            )
        ))
        mock_init.return_value = mock_model

        node = make_compressor_node(cfg=test_cfg)
        state_with_results["findings_summary"] = ""
        result = await node(state_with_results)

        assert "findings_summary" in result
        assert "CONFIRMED" in result["findings_summary"]

    @pytest.mark.asyncio
    @patch("network_operator.nodes.compressor.init_chat_model")
    async def test_compressor_skips_when_no_new_results(self, mock_init, test_cfg, state_with_results):
        mock_model = MagicMock()
        mock_model.ainvoke = AsyncMock()
        mock_init.return_value = mock_model

        node = make_compressor_node(cfg=test_cfg)
        result = await node(state_with_results)

        # step_id already in findings_summary — no model call expected
        mock_model.ainvoke.assert_not_called()
        assert result == {}


# ─────────────────────────────────────────────────────────────────────────────
# Synthesizer node tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSynthesizerNode:
    def _rca(self, confidence="high") -> RCAOutput:
        return RCAOutput(
            executive_summary="BGP flapping caused by MTU mismatch on ge-0/0/2.",
            steps_executed=[StepSummary(
                step_id="check_interface_errors_ge002",
                finding="4,821 giant drops, MTU=9000",
                status="confirmed",
            )],
            hypotheses_evaluated=[HypothesisEvaluated(
                hypothesis_id="H1",
                description="MTU mismatch",
                status="confirmed",
                evidence="4821 giant frame drops",
            )],
            root_cause="MTU mismatch: core-router-1 (9000) vs isp-peer-2 (1500) causing hold-timer expiry.",
            confidence=confidence,
            confidence_reasoning="Two independent data points. No competing hypothesis.",
            proposed_solution="Align MTU or configure ip tcp adjust-mss 1452." if confidence != "undetermined" else None,
            remediation_steps=["[CHANGE REQUIRED] Configure ip tcp adjust-mss 1452"] if confidence != "undetermined" else [],
            gaps_and_open_questions=["ISP-side MTU not directly verified"],
            follow_up_investigations=["Add MTU audit to weekly checks"],
            replan_count=0,
        )

    @pytest.mark.asyncio
    @patch("network_operator.nodes.synthesizer.init_chat_model")
    async def test_synthesizer_produces_rca(self, mock_init, test_cfg, state_with_results):
        mock_model = MagicMock()
        structured = MagicMock()
        structured.ainvoke = AsyncMock(return_value={
            "parsed": self._rca("high"),
            "parsing_error": None,
        })
        mock_model.with_structured_output.return_value = structured
        mock_init.return_value = mock_model

        node = make_synthesizer_node(cfg=test_cfg)
        result = await node(state_with_results)

        assert "rca" in result
        assert result["confidence"] == "high"
        assert "ROOT CAUSE ANALYSIS" in result["rca"]
        assert "MTU" in result["rca"]

    @pytest.mark.asyncio
    @patch("network_operator.nodes.synthesizer.init_chat_model")
    async def test_synthesizer_falls_back_on_parse_error(self, mock_init, test_cfg, state_with_results):
        mock_model = MagicMock()
        structured = MagicMock()
        structured.ainvoke = AsyncMock(return_value={
            "parsed": None,
            "parsing_error": "model returned garbage",
        })
        mock_model.with_structured_output.return_value = structured
        mock_init.return_value = mock_model

        node = make_synthesizer_node(cfg=test_cfg)
        result = await node(state_with_results)

        assert result["confidence"] == "undetermined"
        assert "error" in result["rca"].lower()

    @pytest.mark.asyncio
    @patch("network_operator.nodes.synthesizer.init_chat_model")
    async def test_synthesizer_gaps_always_present(self, mock_init, test_cfg, state_with_results):
        mock_model = MagicMock()
        structured = MagicMock()
        structured.ainvoke = AsyncMock(return_value={
            "parsed": self._rca("high"),
            "parsing_error": None,
        })
        mock_model.with_structured_output.return_value = structured
        mock_init.return_value = mock_model

        node = make_synthesizer_node(cfg=test_cfg)
        result = await node(state_with_results)

        assert "GAPS AND OPEN QUESTIONS" in result["rca"]
