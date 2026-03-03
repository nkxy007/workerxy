"""
nodes/planner.py  (async)
-------------------------
The Planner node — the cognitive core of network_operator.

All I/O is async:
  - ainvoke() on the structured planner model
  - async def planner_node() so LangGraph runs it on the event loop

Everything else (prompt building, state helpers) stays synchronous —
they are CPU-bound pure functions and don't need to be async.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from network_operator.config import NetworkOperatorConfig, DEFAULT_CONFIG
from network_operator.state import (
    AgentState,
    PlannerOutput,
    count_completed_steps,
    get_pending_steps,
)
from network_operator.prompts import PromptRegistry

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Prompt builder  (sync — pure string manipulation)
# ─────────────────────────────────────────────────────────────────────────────

def _build_planner_human_message(state: AgentState, cfg: NetworkOperatorConfig) -> str:
    is_first_call = not state.get("plan_steps") and not state.get("findings_summary")
    pending = get_pending_steps(state)
    completed = count_completed_steps(state)
    total = len(state.get("plan_steps", []))

    sections: list[str] = [f"## Problem Statement\n{state['problem_statement']}"]

    if is_first_call:
        sections.append(
            "## Mode\nFIRST INVOCATION — no prior context or plan exists.\n"
            "Begin with context gathering (read_file, search_internet tools) "
            "before forming any hypothesis."
        )
    else:
        sections.append(
            f"## Mode\nREVIEW INVOCATION — {completed}/{total} steps completed, "
            f"{len(pending)} pending.\n"
            f"Replan count: {state.get('replan_count', 0)}/{cfg.max_replans}."
        )

    if state.get("context_summary"):
        sections.append(f"## Context Summary\n{state['context_summary']}")

    if state.get("hypotheses"):
        hyp_lines = [
            f"  [{h['id']}] {h['status'].upper()} — {h['description']}"
            + (f" | Evidence: {h['evidence']}" if h.get("evidence") else "")
            for h in state["hypotheses"]
        ]
        sections.append("## Current Hypotheses\n" + "\n".join(hyp_lines))

    if state.get("plan_steps"):
        step_lines = [
            f"  [{s['status'].upper()}] {s['id']} → {s['description']} "
            f"(host: {s['target_host']}, destructive: {s['destructive']})"
            for s in state["plan_steps"]
        ]
        sections.append("## Plan Steps\n" + "\n".join(step_lines))

    if state.get("findings_summary"):
        sections.append(f"## Findings Summary (from Compressor)\n{state['findings_summary']}")
    elif state.get("step_results") and not is_first_call:
        sections.append(
            "## Raw Step Results (compressor not yet run)\n"
            + "\n".join(
                f"  [{r['step_id']}] {r['status']} — {r['finding']}"
                for r in state["step_results"]
            )
        )

    if state.get("planner_reasoning"):
        sections.append(
            f"## Your Previous Reasoning\n{state['planner_reasoning']}\n"
            "(Review this — do not contradict your prior reasoning without explanation.)"
        )

    sections.append(
        f"## Constraints\n"
        f"- Max replans remaining: {cfg.max_replans - state.get('replan_count', 0)}\n"
        f"- Max total steps remaining: {cfg.max_steps - total}\n"
        f"- Step IDs already used: {[s['id'] for s in state.get('plan_steps', [])]}\n"
        "  (Do not reuse any of these IDs in new steps.)"
    )

    sections.append(
        "## Your Task\n"
        "Produce a PlannerOutput JSON object.\n"
        "Always populate `reasoning` with at least 2 substantive sentences.\n"
        "Set `next_action` to 'execute' or 'synthesize'.\n"
        "If 'execute': set `current_step_id` to the next pending step to run."
    )

    return "\n\n".join(sections)


# ─────────────────────────────────────────────────────────────────────────────
# Node factory
# ─────────────────────────────────────────────────────────────────────────────

def make_planner_node(
    cfg: NetworkOperatorConfig = DEFAULT_CONFIG,
    prompts: PromptRegistry | None = None,
):
    """
    Factory that returns an async planner_node coroutine function.

    LangGraph detects async nodes automatically and runs them on the event loop.
    No changes needed to the graph topology — just swap sync nodes for async ones.
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

    model_kwargs: dict[str, Any] = {"temperature": cfg.planner_temperature}
    if cfg.planner_thinking_budget > 0:
        model_kwargs["thinking"] = {
            "type": "enabled",
            "budget_tokens": cfg.planner_thinking_budget,
        }

    base_model = init_chat_model(
        model=cfg.reasoning_model,
        model_provider="anthropic",
        **model_kwargs,
    )
    # with_structured_output exposes ainvoke() on the returned runnable
    structured_planner = base_model.with_structured_output(
        PlannerOutput,
        include_raw=True,
    )

    system_message = SystemMessage(content=prompts.planner)

    async def planner_node(state: AgentState) -> dict:
        """
        Async planner node.  Called by LangGraph on every planner visit.
        Awaits the LLM — never blocks the event loop.
        """
        human_content = _build_planner_human_message(state, cfg)
        logger.info(
            "Planner invoked | replan_count=%d | pending_steps=%d",
            state.get("replan_count", 0),
            len(get_pending_steps(state)),
        )

        last_error: Exception | None = None

        for attempt in range(cfg.planner_validation_retries):
            messages_for_model = [system_message, HumanMessage(content=human_content)]

            if last_error and attempt > 0:
                messages_for_model.append(
                    HumanMessage(
                        content=(
                            f"Your previous output failed schema validation "
                            f"(attempt {attempt}/{cfg.planner_validation_retries}):\n"
                            f"{last_error}\n\n"
                            "Please output valid JSON matching the PlannerOutput schema. "
                            "Ensure `reasoning` is at least 10 words and `current_step_id` "
                            "is set when next_action='execute'."
                        )
                    )
                )

            try:
                # ← async call — yields control to the event loop while waiting
                print(f"\n--- PLANNER: THINKING (Attempt {attempt + 1}) ---", flush=True)
                raw_result = await structured_planner.ainvoke(messages_for_model)

                if isinstance(raw_result, dict):
                    if raw_result.get("parsing_error"):
                        raise ValueError(raw_result["parsing_error"])
                    planner_output: PlannerOutput = raw_result["parsed"]
                else:
                    planner_output = raw_result

                print(f"--- PLANNER DECISION: {planner_output.next_action.upper()} ---", flush=True)
                print(f"Reasoning: {planner_output.reasoning}\n", flush=True)

                logger.info(
                    "Planner decision: next_action=%s | reasoning_words=%d",
                    planner_output.next_action,
                    len(planner_output.reasoning.split()),
                )
                patch = planner_output.to_state_patch()
                if planner_output.replan_triggered:
                    patch["replan_count"] = state.get("replan_count", 0) + 1
                return patch

            except (ValidationError, ValueError, KeyError) as e:
                last_error = e
                logger.warning(
                    "Planner schema validation failed (attempt %d/%d): %s",
                    attempt + 1,
                    cfg.planner_validation_retries,
                    e,
                )

        logger.error(
            "Planner failed all %d validation attempts. Routing to synthesizer.",
            cfg.planner_validation_retries,
        )
        return {
            "next_action": "synthesize",
            "planner_reasoning": (
                f"Planner failed to produce valid structured output after "
                f"{cfg.planner_validation_retries} attempts. "
                f"Last error: {last_error}. "
                "Routing to synthesizer to produce a partial RCA from available evidence."
            ),
        }

    return planner_node
