"""
tests/conftest.py  (async)
--------------------------
Shared pytest fixtures for async network_operator tests.

Key differences vs sync version:
  - Mock tools are async (defined with async def or AsyncMock)
  - LangChain tools that get bound to async models must support ainvoke()
  - AsyncMock is used for model methods instead of MagicMock
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool

from network_operator.config import NetworkOperatorConfig
from network_operator.state import (
    AgentState,
    Hypothesis,
    PlanStep,
    StepResult,
    initial_state,
)


# ─────────────────────────────────────────────────────────────────────────────
# Config fixture
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def test_cfg() -> NetworkOperatorConfig:
    return NetworkOperatorConfig(
        reasoning_model="anthropic/claude-3-5-haiku-20241022",
        execution_model="anthropic/claude-3-5-haiku-20241022",
        synthesis_model="anthropic/claude-3-5-haiku-20241022",
        planner_thinking_budget=0,
        max_replans=2,
        max_steps=5,
        max_tool_calls_per_step=3,
        org_name="Test Corp",
        platform_hints="All devices are mocked.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Async mock tools
# MCP tools must support ainvoke() — define them with async def
# ─────────────────────────────────────────────────────────────────────────────

@tool
async def net_run_commands_on_device(device_management_ip: str, commands: list[str], intention: str) -> str:
    """Async mock SSH tool."""
    command = commands[0] if commands else ""
    if "bgp" in command.lower():
        return (
            "BGP neighbor 203.0.113.1 is Up\n"
            "  Hold timer: 180 seconds (configured), keepalive: 60 seconds\n"
            "  Last reset: 00:04:01 ago, due to Holdtime expired\n"
        )
    if "interface" in command.lower():
        return (
            "ge-0/0/2, Physical link is Up\n"
            "  Input Giants: 4821\n"
            "  MTU: 9000 bytes\n"
        )
    if "cpu" in command.lower():
        return "CPU utilization: 12% (5-min average)\n"
    return f"[async mock ssh: {command} on {device_management_ip}]"


@tool
async def execute_shell_command(command: str, intention: str) -> str:
    """Async mock shell tool."""
    if "ping" in command:
        return "2 packets transmitted, 2 received, 0% packet loss\n"
    return f"[async mock shell: {command}]"


@tool
async def mock_read_file(path: str) -> str:
    """Async mock file read tool."""
    if "topology" in path or "changes" in path:
        return (
            "# Recent Changes\n"
            "2024-01-15 14:32 UTC - core-router-1: MTU changed on ge-0/0/2\n"
        )
    return f"[async mock file: {path}]"


@tool
async def mock_search_internet(query: str) -> str:
    """Async mock search tool."""
    return f"[async mock search: {query}] — MTU mismatch causes BGP hold-timer expiry."


@tool
async def execute_generated_code(code: str, intention: str, mode: str = "docker") -> str:
    """Async mock code execution tool."""
    return f"[async mock code execution in {mode} mode: result=42]"


@pytest.fixture
def mock_tools():
    return [
        net_run_commands_on_device,
        execute_shell_command,
        mock_read_file,
        mock_search_internet,
        execute_generated_code,
    ]


# ─────────────────────────────────────────────────────────────────────────────
# State fixtures  (identical to sync version — state is not async)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def blank_state() -> AgentState:
    return initial_state("BGP session between core-router-1 and isp-peer-2 keeps flapping")


@pytest.fixture
def state_with_plan() -> AgentState:
    state = initial_state("BGP flapping on core-router-1")
    state["context_summary"] = "Recent MTU change detected on ge-0/0/2 (CHG-20240115-001)."
    state["hypotheses"] = [
        Hypothesis(id="H1", description="MTU mismatch causing giant frame drops", status="pending", evidence="").model_dump(),
        Hypothesis(id="H2", description="CPU spike causing hold-timer miss", status="pending", evidence="").model_dump(),
    ]
    state["plan_steps"] = [
        PlanStep(
            id="check_interface_errors_ge002",
            hypothesis_id="H1",
            description="Check ge-0/0/2 for giant frame drops and MTU setting",
            target_host="core-router-1",
            tool_category="ssh",
            command_hint="show interfaces ge-0/0/2 detail",
            expected_result="No giant frame drops; MTU consistent with peer",
            destructive=False,
            status="pending",
            skip_reason="",
        ).model_dump(),
        PlanStep(
            id="check_cpu_core_r1",
            hypothesis_id="H2",
            description="Check CPU utilisation during flap window",
            target_host="core-router-1",
            tool_category="ssh",
            command_hint="show system processes summary",
            expected_result="CPU < 70% sustained",
            destructive=False,
            status="pending",
            skip_reason="",
        ).model_dump(),
    ]
    state["current_step_id"] = "check_interface_errors_ge002"
    state["next_action"] = "execute"
    state["planner_reasoning"] = "MTU change found in changelog. H1 is highest priority."
    return state


@pytest.fixture
def state_with_results(state_with_plan) -> AgentState:
    state = dict(state_with_plan)
    state["plan_steps"] = [
        {**state["plan_steps"][0], "status": "done"},
        state["plan_steps"][1],
    ]
    state["step_results"] = [
        StepResult(
            step_id="check_interface_errors_ge002",
            raw_output="ge-0/0/2 ... Giants: 4821 ... MTU: 9000",
            status="confirmed",
            finding=(
                "Interface ge-0/0/2 shows 4,821 giant frame drops in last hour. "
                "MTU configured as 9000 on router. Expected zero giants for healthy MTU alignment. "
                "NOTE: Drop count increasing at roughly 80/minute."
            ),
        ).model_dump()
    ]
    state["findings_summary"] = (
        "## Hypotheses Status\n"
        "[H1] MTU mismatch — CONFIRMED | Evidence: 4,821 giant frame drops on ge-0/0/2\n"
        "[H2] CPU spike — PENDING\n\n"
        "## Steps Completed\n"
        "[check_interface_errors_ge002] — CONFIRMED — 4,821 giant drops, MTU=9000\n\n"
        "## Key Observations\n"
        "• Giant frame counter increasing at ~80/min on ge-0/0/2\n\n"
        "## Outstanding Questions\n"
        "• ISP peer MTU not yet verified"
    )
    state["hypotheses"][0]["status"] = "confirmed"
    state["hypotheses"][0]["evidence"] = "4,821 giant frame drops on ge-0/0/2"
    state["current_step_id"] = "check_cpu_core_r1"
    return AgentState(**state)


# ─────────────────────────────────────────────────────────────────────────────
# Async mock model builder helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_async_structured_model(return_value: dict):
    """
    Returns a mock that behaves like model.with_structured_output().
    ainvoke() is an AsyncMock so it can be awaited in async node tests.
    """
    mock = MagicMock()
    mock.ainvoke = AsyncMock(return_value=return_value)
    return mock


def make_async_tool_model(return_value):
    """
    Returns a mock that behaves like model.bind_tools().
    ainvoke() is an AsyncMock.
    """
    mock = MagicMock()
    mock.ainvoke = AsyncMock(return_value=return_value)
    return mock
