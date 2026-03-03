"""
nodes/synthesizer.py  (async)
------------------------------
The Synthesizer node — produces the final Root Cause Analysis document.

Async changes:
  - synthesizer_node is async def
  - structured_synthesizer.invoke() → await .ainvoke()

The RCA formatter (_format_rca_document) and fallback (_fallback_rca) are
synchronous — they are pure data transformations with no I/O.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from network_operator.config import NetworkOperatorConfig, DEFAULT_CONFIG
from network_operator.state import (
    AgentState,
    RCAOutput,
    HypothesisEvaluated,
    StepSummary,
    count_completed_steps,
)
from network_operator.prompts import PromptRegistry

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Prompt builder  (sync)
# ─────────────────────────────────────────────────────────────────────────────

def _build_synthesizer_human_message(state: AgentState) -> str:
    steps_text = "\n".join(
        f"  [{s['status'].upper()}] {s['id']}\n"
        f"    Hypothesis: {s['hypothesis_id']}\n"
        f"    Description: {s['description']}\n"
        f"    Target: {s['target_host']}\n"
        f"    Expected: {s['expected_result']}\n"
        f"    Destructive: {s['destructive']}"
        + (f"\n    Skip reason: {s.get('skip_reason', '')}" if s["status"] == "skipped" else "")
        for s in state.get("plan_steps", [])
    ) or "  No steps were executed."

    results_text = "\n".join(
        f"  [{r['step_id']}] {r['status'].upper()}\n    Finding: {r['finding']}"
        for r in state.get("step_results", [])
    ) or "  No results recorded."

    hypotheses_text = "\n".join(
        f"  [{h['id']}] {h['status'].upper()} — {h['description']}"
        + (f"\n    Evidence: {h['evidence']}" if h.get("evidence") else "")
        for h in state.get("hypotheses", [])
    ) or "  No hypotheses were formed."

    replan_count = state.get("replan_count", 0)
    replan_note = (
        f"  The investigation was replanned {replan_count} time(s)."
        if replan_count > 0
        else "  No replanning was required."
    )

    completed = count_completed_steps(state)
    total = len(state.get("plan_steps", []))

    return (
        f"## Problem Statement\n{state.get('problem_statement', 'Not provided.')}\n\n"
        f"## Context Summary (gathered before investigation)\n"
        f"{state.get('context_summary', 'Not gathered.') or 'Not gathered.'}\n\n"
        f"## Hypotheses\n{hypotheses_text}\n\n"
        f"## Plan Steps ({completed}/{total} completed)\n{steps_text}\n\n"
        f"## Step Results\n{results_text}\n\n"
        f"## Distilled Findings Summary\n"
        f"{state.get('findings_summary', 'Not available.') or 'Not available.'}\n\n"
        f"## Investigation Metadata\n"
        f"{replan_note}\n"
        f"  Planner's final reasoning: {state.get('planner_reasoning', 'Not recorded.')}\n\n"
        f"## Your Task\n"
        f"Produce a complete RCAOutput JSON object covering ALL sections defined "
        f"in your system prompt.\n"
        f"Be honest about confidence. Populate gaps_and_open_questions even if "
        f"confidence is high.\n"
        f"Root cause must be a CAUSE, not a symptom. "
        f"'Undetermined' is an acceptable root_cause when evidence is insufficient."
    )


# ─────────────────────────────────────────────────────────────────────────────
# RCA formatter  (sync — pure data transformation)
# ─────────────────────────────────────────────────────────────────────────────

def _format_rca_document(rca: RCAOutput, state: AgentState) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    bar = "=" * 72

    confidence_badge = {
        "high": "✓ HIGH",
        "medium": "~ MEDIUM",
        "low": "⚠ LOW",
        "undetermined": "✗ UNDETERMINED",
    }.get(rca.confidence, rca.confidence.upper())

    status = (
        "ROOT CAUSE IDENTIFIED"
        if rca.confidence in ("high", "medium")
        else "INVESTIGATION INCOMPLETE"
    )

    lines: list[str] = [
        bar,
        "INCIDENT ROOT CAUSE ANALYSIS",
        bar,
        f"Date:           {now}",
        f"Confidence:     {confidence_badge}",
        f"Status:         {status}",
        f"Replans:        {rca.replan_count}",
        "",
        "EXECUTIVE SUMMARY",
        bar,
        rca.executive_summary,
        "",
        "PROBLEM STATEMENT",
        bar,
        state.get("problem_statement", "Not provided."),
        "",
        "INVESTIGATION TIMELINE",
        bar,
    ]

    for step in rca.steps_executed:
        lines.append(f"  [{step.step_id}] {step.status.upper()} — {step.finding}")

    lines += ["", "HYPOTHESES EVALUATED", bar]
    for h in rca.hypotheses_evaluated:
        lines.extend([
            f"  [{h.hypothesis_id}] {h.description}",
            f"    Status:   {h.status.upper()}",
            f"    Evidence: {h.evidence}",
            "",
        ])

    lines += [
        "ROOT CAUSE",
        bar,
        rca.root_cause,
        "",
        f"Confidence: {confidence_badge}",
        f"Reasoning:  {rca.confidence_reasoning}",
    ]

    if rca.proposed_solution:
        lines += ["", "PROPOSED SOLUTION", bar, rca.proposed_solution]

    if rca.remediation_steps:
        lines += ["", "REMEDIATION STEPS", bar]
        for i, step in enumerate(rca.remediation_steps, 1):
            lines.append(f"  {i}. {step}")

    lines += ["", "GAPS AND OPEN QUESTIONS", bar]
    if rca.gaps_and_open_questions:
        for gap in rca.gaps_and_open_questions:
            lines.append(f"  • {gap}")
    else:
        lines.append("  No significant gaps identified.")

    if rca.follow_up_investigations:
        lines += ["", "FOLLOW-UP ACTIONS", bar]
        for item in rca.follow_up_investigations:
            lines.append(f"  → {item}")

    lines += ["", bar]
    return "\n".join(lines)


def _fallback_rca(state: AgentState, error: str) -> RCAOutput:
    """Sync fallback — no I/O, no await needed."""
    step_summaries = []
    for r in state.get("step_results", []):
        try:
            step_summaries.append(StepSummary(
                step_id=r["step_id"],
                finding=r["finding"],
                status=r["status"],
            ))
        except Exception:
            pass

    hyp_evaluated = []
    for h in state.get("hypotheses", []):
        try:
            hyp_evaluated.append(HypothesisEvaluated(
                hypothesis_id=h["id"],
                description=h["description"],
                status=h["status"] if h["status"] != "pending" else "not_evaluated",
                evidence=h.get("evidence", ""),
            ))
        except Exception:
            pass

    return RCAOutput(
        executive_summary=(
            "RCA synthesis encountered an error during structured output generation. "
            "A partial summary has been produced from raw investigation data. "
            "Manual review of step results is required."
        ),
        steps_executed=step_summaries,
        hypotheses_evaluated=hyp_evaluated,
        root_cause="Undetermined — synthesizer output error. See step results for raw findings.",
        confidence="undetermined",
        confidence_reasoning=f"Synthesizer failed to produce structured output: {error}",
        proposed_solution=None,
        remediation_steps=[],
        gaps_and_open_questions=[
            "Synthesizer structured output failed — full investigation data is in agent state.",
            f"Error: {error}",
        ],
        follow_up_investigations=["Manual review of agent state step_results required."],
        replan_count=state.get("replan_count", 0),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Node factory
# ─────────────────────────────────────────────────────────────────────────────

def make_synthesizer_node(
    cfg: NetworkOperatorConfig = DEFAULT_CONFIG,
    prompts: PromptRegistry | None = None,
):
    """Factory returning an async synthesizer_node coroutine."""
    if prompts is None:
        prompts = PromptRegistry(
            org_name=cfg.org_name,
            platform_hints=cfg.platform_hints,
            max_replans=cfg.max_replans,
            max_steps=cfg.max_steps,
            rca_audience=cfg.rca_audience,
            include_remediation=cfg.include_remediation,
        )

    model = init_chat_model(
        model=cfg.synthesis_model,
        model_provider="anthropic",
        temperature=0,
        max_tokens=4096,
    )
    structured_synthesizer = model.with_structured_output(RCAOutput, include_raw=True)

    system_message = SystemMessage(content=prompts.synthesizer)

    async def synthesizer_node(state: AgentState) -> dict:
        """
        Async synthesizer node.
        Awaits the LLM call, then formats the result synchronously.
        """
        logger.info(
            "Synthesizer invoked | hypotheses=%d | step_results=%d | replan_count=%d",
            len(state.get("hypotheses", [])),
            len(state.get("step_results", [])),
            state.get("replan_count", 0),
        )

        human_content = _build_synthesizer_human_message(state)

        try:
            # ← async call
            print("\n--- SYNTHESIZER: DRAFTING ROOT CAUSE ANALYSIS ---", flush=True)
            raw_result = await structured_synthesizer.ainvoke(
                [system_message, HumanMessage(content=human_content)]
            )

            if isinstance(raw_result, dict):
                if raw_result.get("parsing_error"):
                    raise ValueError(raw_result["parsing_error"])
                rca_output: RCAOutput = raw_result["parsed"]
            else:
                rca_output = raw_result

        except (ValidationError, ValueError) as e:
            logger.error("Synthesizer structured output failed: %s — falling back.", e)
            rca_output = _fallback_rca(state, error=str(e))

        rca_output.replan_count = state.get("replan_count", 0)
        rca_document = _format_rca_document(rca_output, state)
        
        print(f"\n--- SYNTHESIZER: RCA COMPLETE ---\n{rca_document}\n", flush=True)

        logger.info(
            "Synthesizer complete | confidence=%s | rca_chars=%d",
            rca_output.confidence,
            len(rca_document),
        )

        return {
            "rca": rca_document,
            "proposed_solution": rca_output.proposed_solution,
            "confidence": rca_output.confidence,
        }

    return synthesizer_node
