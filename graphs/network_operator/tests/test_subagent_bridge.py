"""
tests/test_subagent_bridge.py
------------------------------
Unit tests for the subagent_bridge module.

All tests mock the graph nodes so no API keys or running MCP server are needed.
Run with the project conda environment:

    pytest graphs/network_operator/tests/test_subagent_bridge.py -v

"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from network_operator.subagent_bridge import (
    _extract_problem,
    _format_output,
    get_datacenter_subagent,
)
from network_operator.state import initial_state


# ─────────────────────────────────────────────────────────────────────────────
# _extract_problem — input state adapter
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractProblem:
    def test_extracts_last_human_message(self):
        """Should use the last HumanMessage content as problem_statement."""
        messages_state = {
            "messages": [
                HumanMessage(content="First question"),
                AIMessage(content="Some AI reply"),
                HumanMessage(content="BGP flapping on spine-1, investigate please"),
            ]
        }
        result = _extract_problem(messages_state)

        assert result["problem_statement"] == "BGP flapping on spine-1, investigate please"

    def test_skips_non_human_messages(self):
        """With only an AIMessage present, should fall back to the last message."""
        messages_state = {
            "messages": [
                AIMessage(content="I already answered"),
            ]
        }
        result = _extract_problem(messages_state)

        # Falls back to last message content
        assert "already answered" in result["problem_statement"]

    def test_empty_messages_uses_fallback(self):
        """Empty messages list should produce a sensible fallback problem_statement."""
        result = _extract_problem({"messages": []})

        assert isinstance(result["problem_statement"], str)
        assert len(result["problem_statement"]) > 0

    def test_returns_valid_initial_state_keys(self):
        """Returned dict must have all keys that initial_state() produces."""
        messages_state = {
            "messages": [HumanMessage(content="OSPF neighbour down on leaf-3")]
        }
        result = _extract_problem(messages_state)

        expected_keys = set(initial_state("dummy").keys())
        assert expected_keys.issubset(result.keys())

    def test_system_message_not_used_as_problem(self):
        """SystemMessage should not be treated as the human problem statement."""
        messages_state = {
            "messages": [
                SystemMessage(content="You are an expert"),
                HumanMessage(content="VXLAN fabric is unreachable"),
            ]
        }
        result = _extract_problem(messages_state)

        assert result["problem_statement"] == "VXLAN fabric is unreachable"


# ─────────────────────────────────────────────────────────────────────────────
# _format_output — output state adapter
# ─────────────────────────────────────────────────────────────────────────────

class TestFormatOutput:
    def test_rca_wrapped_in_ai_message(self):
        """When rca is present it should be the content of the AIMessage."""
        agent_state = {
            "rca": "ROOT CAUSE ANALYSIS\nMTU mismatch on ge-0/0/2.",
            "confidence": "high",
            "messages": [],
        }
        result = _format_output(agent_state)

        assert "messages" in result
        assert len(result["messages"]) == 1
        msg = result["messages"][0]
        assert isinstance(msg, AIMessage)
        assert "MTU mismatch" in msg.content
        # Confidence is prepended
        assert "high" in msg.content

    def test_fallback_to_last_message_if_no_rca(self):
        """With no rca field, use the last message as the output."""
        agent_state = {
            "rca": None,
            "messages": [AIMessage(content="Investigation done, no RCA.")]
        }
        result = _format_output(agent_state)

        msg = result["messages"][0]
        assert "Investigation done" in msg.content

    def test_default_message_when_no_rca_and_no_messages(self):
        """Completely empty state should still return a valid AIMessage."""
        agent_state = {"rca": None, "messages": []}
        result = _format_output(agent_state)

        assert isinstance(result["messages"][0], AIMessage)
        assert len(result["messages"][0].content) > 0

    def test_returns_messages_key(self):
        """Output dict must always have a 'messages' key."""
        result = _format_output({"rca": "Some RCA", "messages": []})
        assert "messages" in result

    def test_confidence_omitted_when_none(self):
        """If confidence is None, content should not contain stray 'None' text."""
        agent_state = {"rca": "RCA content here", "confidence": None, "messages": []}
        result = _format_output(agent_state)
        assert "None" not in result["messages"][0].content


# ─────────────────────────────────────────────────────────────────────────────
# get_datacenter_subagent — factory
# ─────────────────────────────────────────────────────────────────────────────

class TestGetDatacenterSubagent:
    @patch("network_operator.subagent_bridge.build_graph")
    def test_returns_required_keys(self, mock_build_graph, mock_tools):
        """Factory must return a dict with name, description, and runnable keys."""
        mock_build_graph.return_value = MagicMock()

        result = get_datacenter_subagent(tools=mock_tools)

        assert "name" in result
        assert "description" in result
        assert "runnable" in result

    @patch("network_operator.subagent_bridge.build_graph")
    def test_name_is_datacentre_subagent(self, mock_build_graph, mock_tools):
        """Name must match what net_deepagent.py expects."""
        mock_build_graph.return_value = MagicMock()

        result = get_datacenter_subagent(tools=mock_tools)

        assert result["name"] == "datacentre_subagent"

    @patch("network_operator.subagent_bridge.build_graph")
    def test_description_is_non_empty_string(self, mock_build_graph, mock_tools):
        """Description must be a non-empty string for orchestrator routing."""
        mock_build_graph.return_value = MagicMock()

        result = get_datacenter_subagent(tools=mock_tools)

        assert isinstance(result["description"], str)
        assert len(result["description"]) > 10

    @patch("network_operator.subagent_bridge.build_graph")
    def test_build_graph_called_with_tools(self, mock_build_graph, mock_tools):
        """build_graph must receive the provided tools list."""
        mock_build_graph.return_value = MagicMock()

        get_datacenter_subagent(tools=mock_tools)

        mock_build_graph.assert_called_once()
        call_kwargs = mock_build_graph.call_args
        assert call_kwargs.kwargs.get("tools") == mock_tools or call_kwargs.args[0] == mock_tools

    @patch("network_operator.subagent_bridge.build_graph")
    def test_interrupt_flag_passed_through(self, mock_build_graph, mock_tools):
        """interrupt_before_destructive=True should flow through to build_graph."""
        mock_build_graph.return_value = MagicMock()

        get_datacenter_subagent(tools=mock_tools, interrupt_before_destructive=True)

        _, call_kwargs = mock_build_graph.call_args
        assert call_kwargs.get("interrupt_before_destructive") is True

    @patch("network_operator.subagent_bridge.build_graph")
    def test_runnable_is_composable(self, mock_build_graph, mock_tools):
        """Runnable must be a LangChain Runnable (has invoke / ainvoke)."""
        mock_graph = MagicMock()
        mock_graph.__or__ = MagicMock(return_value=mock_graph)
        mock_graph.ainvoke = AsyncMock(return_value={})
        mock_build_graph.return_value = mock_graph

        result = get_datacenter_subagent(tools=mock_tools)

        runnable = result["runnable"]
        assert hasattr(runnable, "invoke") or hasattr(runnable, "ainvoke")


# ─────────────────────────────────────────────────────────────────────────────
# End-to-end pipeline — mock the compiled graph directly
# ─────────────────────────────────────────────────────────────────────────────

class TestSubagentPipelineEndToEnd:
    @pytest.mark.asyncio
    @patch("network_operator.subagent_bridge.build_graph")
    async def test_pipeline_accepts_messages_and_returns_messages(
        self,
        mock_build_graph,
        mock_tools,
        test_cfg,
    ):
        """
        Full adapter pipeline smoke test:
            MessagesState → _extract_problem → (mocked graph) → _format_output → MessagesState

        Mocks build_graph so the test is isolated from the pre-existing executor
        streaming bug in the existing suite. Exercises the full RunnableLambda chain.
        """
        fake_final_state = {
            "rca": "ROOT CAUSE ANALYSIS\nBGP peer reset due to MTU mismatch on fabric link.",
            "confidence": "high",
            "messages": [],
            "problem_statement": "BGP session down between spine-1 and leaf-3",
            "hypotheses": [], "plan_steps": [], "step_results": [],
            "current_step_id": "", "replan_count": 1,
            "next_action": "synthesize", "planner_reasoning": "",
            "context_summary": "", "findings_summary": "",
            "proposed_solution": "Align MTU on both sides.",
        }

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(return_value=fake_final_state)
        mock_graph.return_value = fake_final_state  # Handle direct sync/async calls
        mock_build_graph.return_value = mock_graph

        subagent = get_datacenter_subagent(tools=mock_tools, cfg=test_cfg,
                                           interrupt_before_destructive=False)
        output = await subagent["runnable"].ainvoke({
            "messages": [HumanMessage(content="BGP session down between spine-1 and leaf-3")]
        })

        assert "messages" in output
        assert len(output["messages"]) == 1
        msg = output["messages"][0]
        assert isinstance(msg, AIMessage)
        assert "ROOT CAUSE" in msg.content
        assert "high" in msg.content   # confidence prepended
        assert "BGP" in msg.content

    @pytest.mark.asyncio
    @patch("network_operator.subagent_bridge.build_graph")
    async def test_pipeline_graceful_fallback_when_no_rca(
        self,
        mock_build_graph,
        mock_tools,
        test_cfg,
    ):
        """When rca is None, _format_output falls back to last message content."""
        fake_final_state = {
            "rca": None, "confidence": None,
            "messages": [AIMessage(content="Investigation stopped early.")],
            "problem_statement": "Some issue", "hypotheses": [], "plan_steps": [],
            "step_results": [], "current_step_id": "", "replan_count": 0,
            "next_action": "execute", "planner_reasoning": "",
            "context_summary": "", "findings_summary": "", "proposed_solution": None,
        }

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(return_value=fake_final_state)
        mock_graph.return_value = fake_final_state
        mock_build_graph.return_value = mock_graph

        subagent = get_datacenter_subagent(tools=mock_tools, cfg=test_cfg)
        output = await subagent["runnable"].ainvoke(
            {"messages": [HumanMessage(content="Any issue")]}
        )

        msg = output["messages"][0]
        assert isinstance(msg, AIMessage)
        assert "Investigation stopped early" in msg.content

    @pytest.mark.asyncio
    @patch("network_operator.subagent_bridge.build_graph")
    async def test_problem_statement_extracted_from_human_message(
        self,
        mock_build_graph,
        mock_tools,
        test_cfg,
    ):
        """The problem_statement passed to the graph must come from the last HumanMessage."""
        captured_input = {}

        def capture_call(state, **kwargs):
            captured_input["problem_statement"] = state.get("problem_statement")
            return {
                "rca": "RCA here.", "confidence": "medium", "messages": [],
                "problem_statement": state.get("problem_statement", ""),
                "hypotheses": [], "plan_steps": [], "step_results": [],
                "current_step_id": "", "replan_count": 0,
                "next_action": "synthesize", "planner_reasoning": "",
                "context_summary": "", "findings_summary": "", "proposed_solution": None,
            }

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(side_effect=capture_call)
        mock_graph.side_effect = capture_call
        mock_build_graph.return_value = mock_graph

        subagent = get_datacenter_subagent(tools=mock_tools, cfg=test_cfg)
        await subagent["runnable"].ainvoke({
            "messages": [
                HumanMessage(content="First message"),
                AIMessage(content="Some reply"),
                HumanMessage(content="OSPF neighbour down on core-r1, investigate"),
            ]
        })

        assert captured_input["problem_statement"] == "OSPF neighbour down on core-r1, investigate"

