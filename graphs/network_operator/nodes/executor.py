"""
nodes/executor.py  (async)
--------------------------
The Executor node — runs a single plan step using MCP-provided tools.

Async changes:
  - executor_node is async def
  - model calls use ainvoke()
  - _extract_and_record_result is async and awaits the extractor
  - should_call_tools stays synchronous — LangGraph conditional edges are sync
  - interrupt() is synchronous by design in LangGraph (it uses an exception
    internally to pause the graph, not an awaitable)

MCP tools passed in from outside must support async invocation.
LangGraph's ToolNode calls .ainvoke() on tools automatically when the graph
runs in async mode — no changes needed to the ToolNode itself.
"""

from __future__ import annotations

import logging

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.types import interrupt
from pydantic import ValidationError

from network_operator.config import NetworkOperatorConfig, DEFAULT_CONFIG
from network_operator.state import (
    AgentState,
    PlanStep,
    StepResult,
    StepResultSchema,
    get_current_step,
)
from network_operator.prompts import PromptRegistry

logger = logging.getLogger(__name__)

_DONE = "compressor"
_CALL_TOOLS = "tools"


# ─────────────────────────────────────────────────────────────────────────────
# Prompt builders  (sync — pure string manipulation)
# ─────────────────────────────────────────────────────────────────────────────

def _build_executor_human_message(step: PlanStep, state: AgentState) -> str:
    prior_findings = "\n".join(
        f"  [{r['step_id']}] {r['status']} — {r['finding']}"
        for r in state.get("step_results", [])
    ) or "  None yet."

    return (
        f"  ID:           {step.id}\n"
        f"  Hypothesis:   {step.hypothesis_id}\n"
        f"  Description:  {step.description}\n"
        f"  Target host:  {step.target_host}\n"
        f"  Tool:         {step.tool_category}\n"
        f"  Command hint: {step.command_hint}\n"
        f"  Expected:     {step.expected_result}\n"
        f"  Destructive:  {step.destructive}\n\n"
        f"## Prior Findings (for context only — do not re-run these steps)\n"
        f"{prior_findings}\n\n"
        f"## Your Task\n"
        f"1. Call the appropriate tool as specified in `tool_category`.\n"
        f"2. Read the full output.\n"
        f"3. Compare against `expected_result`.\n"
        f"4. Produce a StepResultSchema JSON with:\n"
        f"   - step_id: '{step.id}'\n"
        f"   - status: confirmed | rejected | ambiguous\n"
        f"   - finding: 1–4 sentences, specific values, honest\n\n"
        f"Do NOT call tools for any step other than the one listed above.\n"
        f"Do NOT run the step on a different host than '{step.target_host}'."
    )


def _build_result_extraction_message(step_id: str) -> str:
    return (
        f"Tool execution is complete. Now produce the StepResultSchema JSON for step '{step_id}'.\n"
        "Include the exact observed values in `finding`. "
        "Set `status` based on how the output compares to expected_result. "
        "Do not reference any step other than this one."
    )


# ─────────────────────────────────────────────────────────────────────────────
# State mutation helpers  (sync — pure list operations)
# ─────────────────────────────────────────────────────────────────────────────

def _mark_step_done(state: AgentState, step_id: str) -> list[dict]:
    return [
        {**s, "status": "done"} if s["id"] == step_id else s
        for s in state["plan_steps"]
    ]


def _mark_step_skipped(state: AgentState, step_id: str, reason: str) -> list[dict]:
    return [
        {**s, "status": "skipped", "skip_reason": reason} if s["id"] == step_id else s
        for s in state["plan_steps"]
    ]


def _append_result(state: AgentState, result: StepResult) -> list[StepResult]:
    return list(state.get("step_results", [])) + [result]


def _collect_tool_output(messages: list) -> str:
    parts = [
        f"[Tool: {m.name}]\n{m.content}"
        for m in messages
        if isinstance(m, ToolMessage)
    ]
    return "\n\n".join(parts) if parts else ""


def _find_preceding_human(messages: list, tool_msg: ToolMessage) -> str | None:
    for i, m in enumerate(messages):
        if m is tool_msg:
            for j in range(i - 1, -1, -1):
                if isinstance(messages[j], HumanMessage):
                    return messages[j].content
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Conditional edge  (sync — LangGraph edges must be sync)
# ─────────────────────────────────────────────────────────────────────────────

def should_call_tools(state: AgentState) -> str:
    """
    Conditional edge function — must be synchronous.
    LangGraph evaluates conditional edges synchronously even in async graphs.
    """
    messages = state.get("messages", [])
    if not messages:
        return _DONE
    last = messages[-1]
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        return _CALL_TOOLS
    return _DONE


# ─────────────────────────────────────────────────────────────────────────────
# Node factory
# ─────────────────────────────────────────────────────────────────────────────

def make_executor_node(
    tools: list,
    cfg: NetworkOperatorConfig = DEFAULT_CONFIG,
    prompts: PromptRegistry | None = None,
):
    """
    Factory returning an async executor_node coroutine.

    MCP tools are expected to support async invocation.
    LangGraph's ToolNode will call .ainvoke() on them automatically.
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

    base_model = init_chat_model(
        model=cfg.execution_model,
        model_provider="anthropic",
        temperature=0,
    )
    model_with_tools = base_model.bind_tools(tools)
    result_extractor = base_model.with_structured_output(StepResultSchema)

    system_message = SystemMessage(content=prompts.executor)

    async def _extract_and_record_result(
        step: PlanStep,
        messages: list,
        state: AgentState,
    ) -> dict:
        """Async helper: ask the model for a structured StepResult and update state."""
        extraction_prompt = _build_result_extraction_message(step.id)
        extraction_messages = messages + [HumanMessage(content=extraction_prompt)]

        try:
            # ← async call
            print(f"\n--- EXECUTOR: EXTRACTING RESULT FOR {step.id} ---", flush=True)
            step_result_schema: StepResultSchema = await result_extractor.ainvoke(
                [system_message] + extraction_messages
            )
            step_result: StepResult = {
                "step_id": step_result_schema.step_id,
                "raw_output": _collect_tool_output(messages),
                "status": step_result_schema.status,
                "finding": step_result_schema.finding,
            }
            print(f"Status: {step_result['status']} | Finding: {step_result['finding']}")
        except (ValidationError, Exception) as e:
            logger.error("Failed to extract StepResult for step %s: %s", step.id, e)
            step_result = {
                "step_id": step.id,
                "raw_output": _collect_tool_output(messages),
                "status": "ambiguous",
                "finding": (
                    f"Result extraction failed: {e}. "
                    "Raw tool output is available but could not be structured. "
                    "Treating as ambiguous."
                ),
            }

        logger.info(
            "Step %s completed | status=%s | finding_words=%d",
            step.id,
            step_result["status"],
            len(step_result["finding"].split()),
        )

        return {
            "messages": messages + extraction_messages[-1:],
            "plan_steps": _mark_step_done(state, step.id),
            "step_results": _append_result(state, step_result),
        }

    async def executor_node(state: AgentState) -> dict:
        """
        Async executor node.

        interrupt() is still synchronous — it raises a special LangGraph
        exception internally and does not need to be awaited.
        All model calls use ainvoke() and yield control to the event loop.
        """
        step = get_current_step(state)
        if step is None:
            logger.error("Executor called but no current_step_id found in state.")
            return {}

        # ── Destructive step gate ────────────────────────────────────────────
        # interrupt() is synchronous in LangGraph — it does NOT need await
        if step.destructive:
            logger.warning(
                "Destructive step detected: %s — interrupting for approval", step.id
            )
            approval = interrupt(
                {
                    "type": "destructive_step_approval",
                    "step_id": step.id,
                    "description": step.description,
                    "target_host": step.target_host,
                    "command_hint": step.command_hint,
                    "message": (
                        f"Step '{step.id}' is marked destructive and may affect live traffic.\n"
                        f"Description: {step.description}\n"
                        f"Target: {step.target_host}\n"
                        f"Intent: {step.command_hint}\n\n"
                        "Respond with {\"approved\": true} to proceed or "
                        "{\"approved\": false, \"reason\": \"...\"} to skip."
                    ),
                }
            )
            if not approval.get("approved", False):
                skip_reason = approval.get("reason", "User rejected destructive step")
                logger.info("Step %s skipped by user: %s", step.id, skip_reason)
                skipped_result: StepResult = {
                    "step_id": step.id,
                    "raw_output": "",
                    "status": "ambiguous",
                    "finding": f"Step skipped by operator: {skip_reason}. Result is ambiguous.",
                }
                return {
                    "plan_steps": _mark_step_skipped(state, step.id, skip_reason),
                    "step_results": _append_result(state, skipped_result),
                    "messages": state.get("messages", []),
                }

        # ── Build message history for this step ──────────────────────────────
        existing_messages = list(state.get("messages", []))
        step_marker = f"[STEP:{step.id}]"

        step_messages_started = any(
            step_marker in (getattr(m, "content", "") or "")
            for m in existing_messages
        )

        if not step_messages_started:
            human_content = f"{step_marker}\n\n{_build_executor_human_message(step, state)}"
            messages = existing_messages + [HumanMessage(content=human_content)]
        else:
            messages = existing_messages

        # ── Check tool call budget ───────────────────────────────────────────
        tool_call_count = sum(
            1 for m in messages
            if isinstance(m, ToolMessage)
            and step_marker in (_find_preceding_human(messages, m) or "")
        )

        if tool_call_count >= cfg.max_tool_calls_per_step:
            logger.warning(
                "Step %s hit max tool calls (%d). Extracting result.",
                step.id,
                cfg.max_tool_calls_per_step,
            )
            return await _extract_and_record_result(step, messages, state)

        # ── Invoke model (async) ─────────────────────────────────────────────
        print(f"\n--- EXECUTOR: RUNNING STEP {step.id} ---", flush=True)
        response_chunk = None
        async for chunk in model_with_tools.astream(
            [system_message] + messages
        ):
            if isinstance(chunk.content, str) and chunk.content:
                print(chunk.content, end="", flush=True)
            elif isinstance(chunk.content, list):
                for block in chunk.content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        print(block["text"], end="", flush=True)
            if response_chunk is None:
                response_chunk = chunk
            else:
                response_chunk += chunk
        print()
        response: AIMessage = response_chunk
        updated_messages = messages + [response]

        if response.tool_calls:
            print(f"--- EXECUTOR: REQUESTING TOOL CALLS: {[tc['name'] for tc in response.tool_calls]} ---", flush=True)
            logger.debug(
                "Executor requesting tool calls for step %s: %s",
                step.id,
                [tc["name"] for tc in response.tool_calls],
            )
            # Return updated messages — LangGraph will route to ToolNode next
            return {"messages": updated_messages}

        # ── No more tool calls — extract result ──────────────────────────────
        return await _extract_and_record_result(step, updated_messages, state)

    return executor_node
