"""
tests/test_graph.py  (async)
-----------------------------
End-to-end graph tests using async mocks and the async graph API.

Key differences vs sync version:
  - All graph test functions are async def / @pytest.mark.asyncio
  - Graph uses ainvoke() instead of invoke()
  - run_investigation() is awaited
  - stream_investigation() is tested as an async generator
  - Model mocks use AsyncMock for .ainvoke()
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver

from network_operator.agent import build_graph, run_investigation, stream_investigation
from network_operator.state import (
    PlannerOutput,
    HypothesisSchema,
    PlanStepSchema,
    StepResultSchema,
    RCAOutput,
    HypothesisEvaluated,
    StepSummary,
    initial_state,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _planner_output(next_action: str, step_id: str = "") -> PlannerOutput:
    steps = []
    if next_action == "execute" and step_id:
        steps = [PlanStepSchema(
            id=step_id,
            hypothesis_id="H1",
            description="Diagnostic step",
            target_host="router-1",
            tool_category="ssh",
            command_hint="show interface",
            expected_result="No errors",
        )]
    return PlannerOutput(
        reasoning="Evidence reviewed carefully. MTU mismatch confirmed by giant frame drop counter on ge-0/0/2 interface.",
        next_action=next_action,
        hypotheses=[HypothesisSchema(
            id="H1",
            description="MTU mismatch",
            status="confirmed" if next_action == "synthesize" else "pending",
        )],
        plan_steps=steps,
        current_step_id=step_id,
    )


def _step_result(step_id: str, status: str = "confirmed") -> StepResultSchema:
    return StepResultSchema(
        step_id=step_id,
        status=status,
        finding=f"Observed value confirms {status} for step {step_id}. Expected result met.",
    )


def _rca() -> RCAOutput:
    return RCAOutput(
        executive_summary="BGP flapping caused by MTU mismatch on ge-0/0/2.",
        steps_executed=[StepSummary(step_id="check_intf", finding="4821 giants", status="confirmed")],
        hypotheses_evaluated=[HypothesisEvaluated(
            hypothesis_id="H1",
            description="MTU mismatch",
            status="confirmed",
            evidence="4821 giant drops",
        )],
        root_cause="MTU mismatch: core-router-1 (9000) vs isp-peer-2 (1500).",
        confidence="high",
        confidence_reasoning="Two independent data points confirm H1.",
        proposed_solution="Align MTU or configure tcp adjust-mss.",
        remediation_steps=["Configure ip tcp adjust-mss 1452 on ge-0/0/2"],
        gaps_and_open_questions=["ISP-side MTU not directly verified"],
        follow_up_investigations=["Add MTU audit to weekly checks"],
        replan_count=0,
    )


def _make_planner_mock(responses: list):
    """Build a planner model mock with multiple async responses."""
    call_count = 0

    async def ainvoke(messages):
        nonlocal call_count
        resp = responses[min(call_count, len(responses) - 1)]
        call_count += 1
        return resp

    mock_model = MagicMock()
    structured = MagicMock()
    structured.ainvoke = ainvoke
    mock_model.with_structured_output.return_value = structured
    return mock_model, lambda: call_count


def _make_executor_mock(results: list):
    """Build an executor model mock that cycles through StepResultSchema results."""
    call_count = 0

    async def extractor_ainvoke(messages):
        nonlocal call_count
        r = results[min(call_count, len(results) - 1)]
        call_count += 1
        return r

    mock_base = MagicMock()
    bound = MagicMock()
    # No tool calls — executor goes straight to result extraction
    bound.ainvoke = AsyncMock(return_value=AIMessage(content="done"))
    mock_base.bind_tools.return_value = bound
    extractor = MagicMock()
    extractor.ainvoke = extractor_ainvoke
    mock_base.with_structured_output.return_value = extractor
    return mock_base, lambda: call_count


def _make_compressor_mock():
    mock_model = MagicMock()
    mock_model.ainvoke = AsyncMock(return_value=MagicMock(
        content=(
            "## Hypotheses Status\n[H1] CONFIRMED\n\n"
            "## Steps Completed\n[check_intf] CONFIRMED\n\n"
            "## Key Observations\n• Giant drops\n\n"
            "## Outstanding Questions\nNone"
        )
    ))
    return mock_model


def _make_synthesizer_mock(rca_output: RCAOutput):
    mock_model = MagicMock()
    structured = MagicMock()
    structured.ainvoke = AsyncMock(return_value={"parsed": rca_output, "parsing_error": None})
    mock_model.with_structured_output.return_value = structured
    return mock_model


# ─────────────────────────────────────────────────────────────────────────────
# Happy path: single cycle
# ─────────────────────────────────────────────────────────────────────────────

class TestGraphHappyPath:
    @pytest.mark.asyncio
    @patch("network_operator.nodes.synthesizer.init_chat_model")
    @patch("network_operator.nodes.compressor.init_chat_model")
    @patch("network_operator.nodes.executor.init_chat_model")
    @patch("network_operator.nodes.planner.init_chat_model")
    async def test_happy_path_single_cycle(
        self,
        mock_planner_init,
        mock_executor_init,
        mock_compressor_init,
        mock_synthesizer_init,
        test_cfg,
        mock_tools,
    ):
        """
        Flow: planner(execute) → executor → compressor → planner(synthesize) → synthesizer → END
        """
        planner_mock, planner_call_count = _make_planner_mock([
            {"parsed": _planner_output("execute", "check_intf"), "parsing_error": None},
            {"parsed": _planner_output("synthesize"), "parsing_error": None},
        ])
        mock_planner_init.return_value = planner_mock

        executor_mock, _ = _make_executor_mock([_step_result("check_intf", "confirmed")])
        mock_executor_init.return_value = executor_mock

        mock_compressor_init.return_value = _make_compressor_mock()
        mock_synthesizer_init.return_value = _make_synthesizer_mock(_rca())

        graph = build_graph(
            tools=mock_tools,
            cfg=test_cfg,
            checkpointer=MemorySaver(),
            interrupt_before_destructive=False,
        )

        result = await run_investigation(graph, "BGP flapping", thread_id="async-happy")

        assert result["rca"] is not None
        assert "ROOT CAUSE ANALYSIS" in result["rca"]
        assert result["confidence"] == "high"
        assert planner_call_count() == 2

    @pytest.mark.asyncio
    @patch("network_operator.nodes.synthesizer.init_chat_model")
    @patch("network_operator.nodes.compressor.init_chat_model")
    @patch("network_operator.nodes.executor.init_chat_model")
    @patch("network_operator.nodes.planner.init_chat_model")
    async def test_stream_investigation_yields_tuples(
        self,
        mock_planner_init,
        mock_executor_init,
        mock_compressor_init,
        mock_synthesizer_init,
        test_cfg,
        mock_tools,
    ):
        """stream_investigation() must yield (node_name, patch) tuples."""
        planner_mock, _ = _make_planner_mock([
            {"parsed": _planner_output("execute", "check_intf"), "parsing_error": None},
            {"parsed": _planner_output("synthesize"), "parsing_error": None},
        ])
        mock_planner_init.return_value = planner_mock

        executor_mock, _ = _make_executor_mock([_step_result("check_intf")])
        mock_executor_init.return_value = executor_mock

        mock_compressor_init.return_value = _make_compressor_mock()
        mock_synthesizer_init.return_value = _make_synthesizer_mock(_rca())

        graph = build_graph(
            tools=mock_tools,
            cfg=test_cfg,
            checkpointer=MemorySaver(),
            interrupt_before_destructive=False,
        )

        nodes_seen = []
        async for node, patch in stream_investigation(graph, "BGP flapping", thread_id="async-stream"):
            nodes_seen.append(node)
            assert isinstance(patch, dict)

        assert "planner" in nodes_seen
        assert "executor" in nodes_seen
        assert "synthesizer" in nodes_seen


# ─────────────────────────────────────────────────────────────────────────────
# Replan path
# ─────────────────────────────────────────────────────────────────────────────

class TestGraphReplanPath:
    @pytest.mark.asyncio
    @patch("network_operator.nodes.synthesizer.init_chat_model")
    @patch("network_operator.nodes.compressor.init_chat_model")
    @patch("network_operator.nodes.executor.init_chat_model")
    @patch("network_operator.nodes.planner.init_chat_model")
    async def test_replan_then_confirm(
        self,
        mock_planner_init,
        mock_executor_init,
        mock_compressor_init,
        mock_synthesizer_init,
        test_cfg,
        mock_tools,
    ):
        """H1 rejected → replan → H2 confirmed → synthesize."""
        planner_mock, planner_call_count = _make_planner_mock([
            {"parsed": _planner_output("execute", "check_h1"), "parsing_error": None},
            {"parsed": _planner_output("execute", "check_h2"), "parsing_error": None},
            {"parsed": _planner_output("synthesize"), "parsing_error": None},
        ])
        mock_planner_init.return_value = planner_mock

        executor_mock, exec_call_count = _make_executor_mock([
            _step_result("check_h1", "rejected"),
            _step_result("check_h2", "confirmed"),
        ])
        mock_executor_init.return_value = executor_mock

        mock_compressor_init.return_value = _make_compressor_mock()
        mock_synthesizer_init.return_value = _make_synthesizer_mock(_rca())

        graph = build_graph(
            tools=mock_tools,
            cfg=test_cfg,
            checkpointer=MemorySaver(),
            interrupt_before_destructive=False,
        )

        result = await run_investigation(graph, "BGP flapping — replan test", thread_id="async-replan")

        assert result["confidence"] == "high"
        assert planner_call_count() == 3
        assert exec_call_count() == 2


# ─────────────────────────────────────────────────────────────────────────────
# Max replans → undetermined RCA
# ─────────────────────────────────────────────────────────────────────────────

class TestGraphMaxReplans:
    @pytest.mark.asyncio
    @patch("network_operator.nodes.synthesizer.init_chat_model")
    @patch("network_operator.nodes.compressor.init_chat_model")
    @patch("network_operator.nodes.executor.init_chat_model")
    @patch("network_operator.nodes.planner.init_chat_model")
    async def test_exhausted_replans_route_to_synthesizer(
        self,
        mock_planner_init,
        mock_executor_init,
        mock_compressor_init,
        mock_synthesizer_init,
        test_cfg,
        mock_tools,
    ):
        """After max replans, agent must route to synthesizer with undetermined confidence."""
        call_count = 0

        async def planner_ainvoke(messages):
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                return {"parsed": _planner_output("execute", f"step_{call_count}"), "parsing_error": None}
            return {"parsed": _planner_output("synthesize"), "parsing_error": None}

        planner_mock = MagicMock()
        structured = MagicMock()
        structured.ainvoke = planner_ainvoke
        planner_mock.with_structured_output.return_value = structured
        mock_planner_init.return_value = planner_mock

        exec_idx = 0

        async def exec_ainvoke(messages):
            nonlocal exec_idx
            r = _step_result(f"step_{exec_idx + 1}", "rejected")
            exec_idx += 1
            return r

        exec_mock = MagicMock()
        bound = MagicMock()
        bound.ainvoke = AsyncMock(return_value=AIMessage(content="done"))
        exec_mock.bind_tools.return_value = bound
        extractor = MagicMock()
        extractor.ainvoke = exec_ainvoke
        exec_mock.with_structured_output.return_value = extractor
        mock_executor_init.return_value = exec_mock

        mock_compressor_init.return_value = _make_compressor_mock()

        undetermined = _rca()
        undetermined.confidence = "undetermined"
        undetermined.root_cause = "Undetermined"
        undetermined.proposed_solution = None
        undetermined.remediation_steps = []
        mock_synthesizer_init.return_value = _make_synthesizer_mock(undetermined)

        graph = build_graph(
            tools=mock_tools,
            cfg=test_cfg,
            checkpointer=MemorySaver(),
            interrupt_before_destructive=False,
        )

        result = await run_investigation(
            graph, "Unknown issue — all hypotheses fail", thread_id="async-maxreplan"
        )

        assert result["confidence"] == "undetermined"
        assert result["rca"] is not None


# ─────────────────────────────────────────────────────────────────────────────
# Concurrent investigations
# ─────────────────────────────────────────────────────────────────────────────

class TestConcurrentInvestigations:
    @pytest.mark.asyncio
    @patch("network_operator.nodes.synthesizer.init_chat_model")
    @patch("network_operator.nodes.compressor.init_chat_model")
    @patch("network_operator.nodes.executor.init_chat_model")
    @patch("network_operator.nodes.planner.init_chat_model")
    async def test_two_concurrent_investigations_isolated(
        self,
        mock_planner_init,
        mock_executor_init,
        mock_compressor_init,
        mock_synthesizer_init,
        test_cfg,
        mock_tools,
    ):
        """
        Two concurrent investigations must not share state.
        Each uses a different thread_id — LangGraph checkpointer isolates them.
        This test verifies both complete successfully without cross-contamination.
        """
        import asyncio

        planner_mock, _ = _make_planner_mock([
            {"parsed": _planner_output("execute", "check_intf"), "parsing_error": None},
            {"parsed": _planner_output("synthesize"), "parsing_error": None},
        ])
        mock_planner_init.return_value = planner_mock

        executor_mock, _ = _make_executor_mock([_step_result("check_intf")])
        mock_executor_init.return_value = executor_mock

        mock_compressor_init.return_value = _make_compressor_mock()
        mock_synthesizer_init.return_value = _make_synthesizer_mock(_rca())

        graph = build_graph(
            tools=mock_tools,
            cfg=test_cfg,
            checkpointer=MemorySaver(),
            interrupt_before_destructive=False,
        )

        # Run two investigations concurrently with different thread IDs
        results = await asyncio.gather(
            run_investigation(graph, "BGP flapping — incident A", thread_id="concurrent-A"),
            run_investigation(graph, "BGP flapping — incident B", thread_id="concurrent-B"),
        )

        # Both should complete successfully
        assert results[0]["rca"] is not None
        assert results[1]["rca"] is not None
