"""
nodes/compressor.py  (async)
-----------------------------
The Compressor node — distils raw step results into a clean findings summary.

Async changes:
  - compressor_node is async def
  - model.invoke() → await model.ainvoke()

Everything else is unchanged — prompt building and state checks are sync.
"""

from __future__ import annotations

import logging

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage

from network_operator.config import NetworkOperatorConfig, DEFAULT_CONFIG
from network_operator.state import AgentState, StepResult
from network_operator.prompts import PromptRegistry

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Prompt builder  (sync)
# ─────────────────────────────────────────────────────────────────────────────

def _build_compressor_human_message(
    state: AgentState,
    cfg: NetworkOperatorConfig,
) -> str:
    existing_summary = state.get("findings_summary", "")
    all_results: list[StepResult] = state.get("step_results", [])

    new_results = [
        r for r in all_results
        if r["step_id"] not in existing_summary
    ]

    if not new_results:
        return ""  # Signal to skip model invocation

    new_results_text = "\n".join(
        f"[{r['step_id']}] STATUS={r['status'].upper()}\n"
        f"  Finding: {r['finding']}\n"
        f"  Raw output (first 800 chars):\n"
        f"  {r['raw_output'][:800]}{'...(truncated)' if len(r['raw_output']) > 800 else ''}"
        for r in new_results
    )

    hypotheses_text = "\n".join(
        f"  [{h['id']}] {h['status'].upper()} — {h['description']}"
        + (f"\n    Evidence: {h['evidence']}" if h.get("evidence") else "")
        for h in state.get("hypotheses", [])
    ) or "  None defined yet."

    return (
        f"## New Step Results to Incorporate\n"
        f"{new_results_text}\n\n"
        f"## Current Hypothesis Statuses\n"
        f"{hypotheses_text}\n\n"
        f"## Existing Findings Summary (update this, do not discard it)\n"
        f"{existing_summary if existing_summary else 'No prior summary — this is the first cycle.'}\n\n"
        f"## Instructions\n"
        f"Produce an updated findings_summary that:\n"
        f"  1. Incorporates ALL new step results above\n"
        f"  2. Preserves relevant information from the existing summary\n"
        f"  3. Updates any entries that have been superseded by new evidence\n"
        f"  4. Uses the exact structure defined in your system prompt\n"
        f"  5. Stays under {cfg.compressor_max_words} words total\n\n"
        f"Output ONLY the findings_summary text. No preamble, no explanation."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Node factory
# ─────────────────────────────────────────────────────────────────────────────

def make_compressor_node(
    cfg: NetworkOperatorConfig = DEFAULT_CONFIG,
    prompts: PromptRegistry | None = None,
):
    """Factory returning an async compressor_node coroutine."""
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
        model=cfg.execution_model,
        model_provider="anthropic",
        temperature=0,
        max_tokens=1024,
    )

    system_message = SystemMessage(content=prompts.compressor)

    async def compressor_node(state: AgentState) -> dict:
        """
        Async compressor node.
        Skips model invocation if no new results exist (avoids unnecessary API calls).
        """
        human_content = _build_compressor_human_message(state, cfg)

        if not human_content:
            logger.debug("Compressor: no new results, skipping.")
            return {}

        logger.info(
            "Compressor running | new_results=%d | existing_summary_words=%d",
            len([
                r for r in state.get("step_results", [])
                if r["step_id"] not in state.get("findings_summary", "")
            ]),
            len(state.get("findings_summary", "").split()),
        )

        # ← async call
        print("\n--- COMPRESSOR: SUMMARIZING FINDINGS ---", flush=True)
        response_chunk = None
        async for chunk in model.astream(
            [system_message, HumanMessage(content=human_content)]
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
        new_summary = response_chunk.content.strip()

        logger.info("Compressor complete | summary_words=%d", len(new_summary.split()))

        return {"findings_summary": new_summary}

    return compressor_node
