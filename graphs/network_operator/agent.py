"""
agent.py  (async)
-----------------
Graph assembly and async public entry point for network_operator.

Key async changes vs the sync version:
  - run_investigation() is async and uses graph.ainvoke() / graph.astream()
  - resume_after_approval() is async
  - stream_investigation() is an async generator yielding node updates in real time
  - build_graph() itself is still synchronous — graph compilation is CPU-bound
    and LangGraph's compile() has no async variant

Usage:
    import asyncio
    from network_operator.agent import build_graph, run_investigation

    graph = build_graph(tools=my_mcp_tools)
    result = asyncio.run(run_investigation(graph, "BGP session flapping on core-router-1"))
    print(result["rca"])

    # Streaming
    async def main():
        async for node, patch in stream_investigation(graph, "BGP flapping"):
            print(f"[{node}] {list(patch.keys())}")

    # FastAPI / Starlette integration example:
    #   result = await run_investigation(graph, problem, thread_id=request_id)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, AsyncIterator, Optional

# Ensure the directory containing 'network_operator' is in sys.path
_parent_dir = str(Path(__file__).resolve().parent.parent)
if _parent_dir not in sys.path:
    sys.path.append(_parent_dir)

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from network_operator.config import NetworkOperatorConfig, DEFAULT_CONFIG
from network_operator.nodes import (
    make_compressor_node,
    make_executor_node,
    make_planner_node,
    make_synthesizer_node,
    should_call_tools,
)
from network_operator.prompts import PromptRegistry
from network_operator.state import AgentState, initial_state

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Graph builder  (sync — compilation is CPU-bound, no async variant needed)
# ─────────────────────────────────────────────────────────────────────────────

def build_graph(
    tools: list,
    cfg: NetworkOperatorConfig = DEFAULT_CONFIG,
    prompts: Optional[PromptRegistry] = None,
    checkpointer=None,
    interrupt_before_destructive: bool = True,
):
    """
    Assemble and compile the network_operator LangGraph agent.

    Graph compilation is synchronous. The async behaviour comes from the node
    coroutines — LangGraph detects async def nodes automatically and schedules
    them on the running event loop via ainvoke()/astream().

    Args:
        tools:                       LangChain tool objects from your MCP integration.
                                     Must support async invocation (.ainvoke()).
                                     LangGraph's ToolNode calls ainvoke() automatically
                                     when the graph runs in async mode.
        cfg:                         Runtime configuration.
        prompts:                     Pre-built PromptRegistry. Built from cfg if None.
        checkpointer:                LangGraph checkpointer for state persistence and
                                     human-in-the-loop resumption.
                                     In async contexts, prefer AsyncSqliteSaver or
                                     AsyncPostgresSaver over MemorySaver for production.
        interrupt_before_destructive: Compile with interrupt_before=["executor"] so
                                     the destructive gate can pause for approval.

    Returns:
        A compiled LangGraph CompiledGraph. Call graph.ainvoke() / graph.astream()
        from async code.
    """
    if prompts is None:
        prompts = PromptRegistry(
            org_name=cfg.org_name,
            platform_hints=cfg.platform_hints,
            max_replans=cfg.max_replans,
            max_steps=cfg.max_steps,
            rca_audience=cfg.rca_audience,
            include_remediation=cfg.include_remediation,
        )

    if checkpointer is None:
        checkpointer = MemorySaver()
        logger.warning(
            "Using in-memory checkpointer. For production async use, prefer "
            "AsyncSqliteSaver or AsyncPostgresSaver from langgraph.checkpoint."
        )

    # All node factories return async coroutine functions
    planner_node    = make_planner_node(cfg=cfg, prompts=prompts)
    executor_node   = make_executor_node(tools=tools, cfg=cfg, prompts=prompts)
    compressor_node = make_compressor_node(cfg=cfg, prompts=prompts)
    synthesizer_node = make_synthesizer_node(cfg=cfg, prompts=prompts)

    # ToolNode handles async tools automatically when called via astream/ainvoke
    tool_node = ToolNode(tools)

    builder = StateGraph(AgentState)

    builder.add_node("planner",     planner_node)
    builder.add_node("executor",    executor_node)
    builder.add_node("tools",       tool_node)
    builder.add_node("compressor",  compressor_node)
    builder.add_node("synthesizer", synthesizer_node)

    builder.set_entry_point("planner")

    # Conditional edges are synchronous — LangGraph evaluates them sync even in async graphs
    builder.add_conditional_edges(
        "planner",
        lambda state: state.get("next_action", "execute"),
        {"execute": "executor", "synthesize": "synthesizer"},
    )

    builder.add_conditional_edges(
        "executor",
        should_call_tools,          # sync conditional edge function
        {"tools": "tools", "compressor": "compressor"},
    )

    builder.add_edge("tools",       "executor")
    builder.add_edge("compressor",  "planner")
    builder.add_edge("synthesizer", END)

    compile_kwargs: dict[str, Any] = {"checkpointer": checkpointer}
    if interrupt_before_destructive:
        compile_kwargs["interrupt_before"] = ["executor"]

    graph = builder.compile(**compile_kwargs)

    logger.info(
        "network_operator graph compiled (async) | model=%s | max_replans=%d | tools=%d",
        cfg.reasoning_model,
        cfg.max_replans,
        len(tools),
    )

    return graph


# ─────────────────────────────────────────────────────────────────────────────
# Async runners
# ─────────────────────────────────────────────────────────────────────────────

async def run_investigation(
    graph,
    problem_statement: str,
    thread_id: str = "default",
) -> AgentState:
    """
    Run a full diagnostic investigation asynchronously.

    Awaits graph.ainvoke() — never blocks the event loop.
    Safe to call from FastAPI, Starlette, or any async framework.

    Args:
        graph:             Compiled graph from build_graph().
        problem_statement: The incident description to investigate.
        thread_id:         Unique ID per incident. Reusing an ID resumes an
                           existing investigation rather than starting fresh.

    Returns:
        The final AgentState after the graph reaches END.

    Human-in-the-loop (destructive steps):
        Graph will pause at the executor node for destructive steps.
        Resume with resume_after_approval().

    Example:
        graph = build_graph(tools=mcp_tools)
        result = await run_investigation(graph, "BGP flapping on core-router-1")
        print(result["rca"])
    """
    config = {"configurable": {"thread_id": thread_id}}
    state = initial_state(problem_statement)
    return await graph.ainvoke(state, config=config)


async def stream_investigation(
    graph,
    problem_statement: str,
    thread_id: str = "default",
) -> AsyncIterator[tuple[str, dict]]:
    """
    Stream a diagnostic investigation, yielding (node_name, state_patch) tuples
    as each node completes.

    Use this when you want to push real-time progress to a UI, WebSocket,
    or logging pipeline without waiting for the full investigation to finish.

    Args:
        graph:             Compiled graph from build_graph().
        problem_statement: The incident description to investigate.
        thread_id:         Unique ID per incident.

    Yields:
        (node_name, state_patch) tuples. state_patch contains only the keys
        that the node modified — not the full state.

    Example:
        async for node, patch in stream_investigation(graph, "BGP flapping"):
            if "rca" in patch:
                print("RCA ready:", patch["rca"][:200])
            else:
                print(f"[{node}] updated: {list(patch.keys())}")
    """
    config = {"configurable": {"thread_id": thread_id}}
    state = initial_state(problem_statement)

    async for chunk in graph.astream(state, config=config, stream_mode="updates"):
        # astream with stream_mode="updates" yields {node_name: state_patch} dicts
        for node_name, patch in chunk.items():
            yield node_name, patch


async def resume_after_approval(
    graph,
    thread_id: str,
    approved: bool,
    reason: str = "",
) -> AgentState:
    """
    Async resume after a destructive step approval decision.

    The graph was paused by interrupt() inside the executor node.
    This sends the approval decision and resumes execution asynchronously.

    Args:
        graph:     The compiled graph that was interrupted.
        thread_id: Thread ID of the interrupted investigation.
        approved:  True to proceed, False to skip the destructive step.
        reason:    Rejection reason (logged in step result when approved=False).

    Returns:
        The final AgentState after the graph completes.

    Example:
        # Resume after a human approved the destructive step via UI
        result = await resume_after_approval(graph, thread_id="incident-42", approved=True)
    """
    from langgraph.types import Command

    config = {"configurable": {"thread_id": thread_id}}
    resume_value: dict = {"approved": approved}
    if not approved and reason:
        resume_value["reason"] = reason

    logger.info(
        "Resuming investigation (async) thread=%s | approved=%s | reason=%s",
        thread_id,
        approved,
        reason or "none",
    )

    return await graph.ainvoke(Command(resume=resume_value), config=config)


async def stream_resume_after_approval(
    graph,
    thread_id: str,
    approved: bool,
    reason: str = "",
) -> AsyncIterator[tuple[str, dict]]:
    """
    Streaming variant of resume_after_approval.
    Yields (node_name, patch) tuples as execution continues after the interrupt.

    Example:
        async for node, patch in stream_resume_after_approval(graph, "incident-42", approved=True):
            print(f"[{node}] {list(patch.keys())}")
    """
    from langgraph.types import Command

    config = {"configurable": {"thread_id": thread_id}}
    resume_value: dict = {"approved": approved}
    if not approved and reason:
        resume_value["reason"] = reason

    async for chunk in graph.astream(
        Command(resume=resume_value), config=config, stream_mode="updates"
    ):
        for node_name, patch in chunk.items():
            yield node_name, patch
