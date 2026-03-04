"""
subagent_bridge.py
------------------
Compiled-subagent integration for network_operator.

Exposes get_datacenter_subagent() which returns a dict understood by
create_deep_agent() in net_deepagent.py — the same pattern used by
graphs/design_interpretor.py.

Dual-mode design
~~~~~~~~~~~~~~~~
• Standalone — agent_launcher.py calls build_graph() + run_investigation()
  directly.  Nothing in this file changes that path.
• Subagent mode — net_deepagent.py calls get_datacenter_subagent() here.
  The returned ``runnable`` is a RunnableLambda chain::

      MessagesState  ──►  _extract_problem  ──►  compiled graph  ──►  _format_output  ──►  MessagesState

  The chain accepts {"messages": [...]} and returns {"messages": [AIMessage(rca)]},
  which is what the deepagent framework expects from any subagent runnable.

Checkpointer note
~~~~~~~~~~~~~~~~~
In subagent mode the graph is compiled with ``checkpointer=False``.
The parent deepagent owns the conversation thread; the subagent is a
stateless function call from LangGraph's perspective.  If you need
human-in-the-loop approval across turns, pass a real checkpointer via
``build_graph()`` directly and manage the thread_id externally.
"""

from __future__ import annotations

import logging
from typing import Optional

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda

from .agent import build_graph
from .config import DEFAULT_CONFIG, NetworkOperatorConfig
from .state import initial_state

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# State adapter helpers
# ─────────────────────────────────────────────────────────────────────────────

def _extract_problem(messages_state: dict) -> dict:
    """
    Convert a MessagesState-compatible dict into network_operator's initial AgentState.

    The deepagent framework passes {"messages": [...]} to subagents.
    We extract the last HumanMessage and use its content as the problem_statement.

    Args:
        messages_state: dict with at minimum a ``"messages"`` key.

    Returns:
        A fully-initialised network_operator AgentState dict ready for graph.ainvoke().
    """
    msgs = messages_state.get("messages", [])
    # Walk backwards to find the most recent human message
    last_human: Optional[str] = None
    for m in reversed(msgs):
        if isinstance(m, HumanMessage):
            last_human = m.content if isinstance(m.content, str) else str(m.content)
            break

    if last_human is None:
        # Fallback: stringify the last message of any type
        last_human = str(msgs[-1].content) if msgs else "Investigate the reported network issue."

    logger.debug("datacentre_subagent: problem_statement = %s", last_human[:120])
    return initial_state(last_human)


def _format_output(agent_state: dict) -> dict:
    """
    Convert network_operator's final AgentState back into MessagesState.

    Extracts the ``rca`` field (populated by the Synthesizer node) and
    wraps it in an AIMessage so the parent agent can read it.

    Args:
        agent_state: Final AgentState dict returned by graph.ainvoke().

    Returns:
        {"messages": [AIMessage(content=rca)]} suitable for MessagesState.
    """
    rca: Optional[str] = agent_state.get("rca")
    confidence: Optional[str] = agent_state.get("confidence")

    if rca:
        content = rca
    else:
        # Graceful degradation: return whatever the last message was
        messages = agent_state.get("messages", [])
        if messages:
            last = messages[-1]
            content = last.content if isinstance(last.content, str) else str(last.content)
        else:
            content = "Data-centre investigation completed. No RCA was generated."

    if confidence:
        content = f"[Confidence: {confidence}]\n\n{content}"

    logger.debug("datacentre_subagent: output length = %d chars", len(content))
    return {"messages": [AIMessage(content=content)]}


# ─────────────────────────────────────────────────────────────────────────────
# Public factory
# ─────────────────────────────────────────────────────────────────────────────

def get_datacenter_subagent(
    tools: list,
    cfg: NetworkOperatorConfig = DEFAULT_CONFIG,
    interrupt_before_destructive: bool = False,
) -> dict:
    """
    Build and return a compiled-subagent configuration dict for net_deepagent.py.

    The dict has the keys expected by create_deep_agent():
        • name        — identifier used in deepagent routing
        • description — natural-language description for the orchestrator
        • runnable    — a LangChain Runnable that the framework invokes

    The runnable is a three-stage pipeline::

        {"messages": [...]}
            ↓ _extract_problem
        AgentState (initial)
            ↓ compiled network_operator graph (ainvoke)
        AgentState (final, with rca field populated)
            ↓ _format_output
        {"messages": [AIMessage(rca)]}

    Args:
        tools:
            LangChain tool objects to pass to the network_operator graph.
            Typically the ``datacentre_``-prefixed MCP tools plus shared
            utilities like search_internet / user_clarification_and_action_tool.
        cfg:
            NetworkOperatorConfig instance.  Defaults to DEFAULT_CONFIG which
            uses the Claude Sonnet reasoning model.  Override per environment:
            ``NetworkOperatorConfig(reasoning_model="openai/o3", max_replans=5)``
        interrupt_before_destructive:
            Set True to pause the graph for human approval before destructive
            steps (changes to live network devices).  Default False for
            subagent mode — the orchestrating agent handles the approval flow.

    Returns:
        dict with keys ``name``, ``description``, ``runnable``.

    Example::

        from graphs.network_operator.subagent_bridge import get_datacenter_subagent

        dc_subagent = get_datacenter_subagent(
            tools=datacenter_tools + [search_internet],
        )
        # Pass to create_deep_agent(..., subagents=[..., dc_subagent])
    """
    logger.info(
        "Building datacentre_subagent | model=%s | tools=%d | interrupt=%s",
        cfg.reasoning_model,
        len(tools),
        interrupt_before_destructive,
    )

    # checkpointer=False: in subagent mode the parent agent owns thread state.
    # This avoids the LangGraph requirement for a thread_id in configurable
    # when using MemorySaver. The subagent is effectively a stateless call.
    compiled_graph = build_graph(
        tools=tools,
        cfg=cfg,
        checkpointer=False,
        interrupt_before_destructive=interrupt_before_destructive,
    )

    runnable = (
        RunnableLambda(_extract_problem)
        | compiled_graph
        | RunnableLambda(_format_output)
    )

    return {
        "name": "datacentre_subagent",
        "description": (
            "Specialist agent for deep data-centre network investigations. "
            "Handles incidents involving spine-leaf fabric, VXLAN/EVPN, BGP/OSPF "
            "routing faults, hardware failures, port and LAG issues, and "
            "data-centre firewall/security policy problems. "
            "The agent forms hypotheses, executes diagnostic commands (SSH, shell, "
            "file reads), compresses findings, and produces a full Root Cause "
            "Analysis (RCA) report with confidence rating and ordered remediation steps. "
            "Provide a natural-language problem statement in your message — include any "
            "known device IPs, error messages, user impact, or recent changes."
        ),
        "runnable": runnable,
    }
