"""
state.py
--------
Shared state schema, Pydantic output models, and state helper utilities
for the network_operator LangGraph agent.

Everything that flows between nodes lives here.
"""

from __future__ import annotations

from typing import Annotated, Literal, Optional
from pydantic import BaseModel, Field, field_validator
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


# ---------------------------------------------------------------------------
# Sub-types
# ---------------------------------------------------------------------------

StepStatus = Literal["pending", "done", "skipped"]
HypothesisStatus = Literal["pending", "confirmed", "rejected", "ambiguous"]
ResultStatus = Literal["confirmed", "rejected", "ambiguous"]
NextAction = Literal["execute", "synthesize"]
ToolCategory = Literal["ssh", "shell", "file_read", "search", "code_exec"]
Confidence = Literal["high", "medium", "low", "undetermined"]


# ---------------------------------------------------------------------------
# Core domain models (Pydantic — used in structured output AND state)
# ---------------------------------------------------------------------------

class Hypothesis(BaseModel):
    """A single root-cause hypothesis formed by the planner."""
    id: str = Field(
        description="Short snake_case identifier, e.g. 'h1_mtu_mismatch'"
    )
    description: str = Field(
        description="Specific, falsifiable description of the hypothesis"
    )
    status: HypothesisStatus = Field(
        default="pending",
        description="Current evaluation status"
    )
    evidence: Optional[str] = Field(
        default=None,
        description="Evidence that led to current status (populated by planner on review)"
    )

    @field_validator("id")
    @classmethod
    def id_must_be_snake_case(cls, v: str) -> str:
        if " " in v:
            raise ValueError(f"Hypothesis id must be snake_case, got: {v!r}")
        return v.lower()


class PlanStep(BaseModel):
    """A single diagnostic step in the plan."""
    id: str = Field(
        description=(
            "Unique semantic snake_case label, e.g. 'check_bgp_hold_timer_core_r1'. "
            "Must be unique across the entire session including replans."
        )
    )
    hypothesis_id: str = Field(
        description="ID of the hypothesis this step validates or invalidates"
    )
    description: str = Field(
        description="One sentence — what are we checking and why"
    )
    target_host: str = Field(
        description=(
            "Exact hostname or IP of the target device. "
            "Use 'local' for steps that run on the agent host."
        )
    )
    tool_category: ToolCategory = Field(
        description="Which tool category the executor should use"
    )
    command_hint: str = Field(
        description=(
            "The intent of the command. The executor picks exact platform syntax. "
            "Example: 'show interfaces ge-0/0/2 detail'"
        )
    )
    expected_result: str = Field(
        description="What a confirming result looks like, with specific values if known"
    )
    destructive: bool = Field(
        default=False,
        description=(
            "True if this step could affect traffic or change device state. "
            "Triggers human-in-the-loop approval gate."
        )
    )
    status: StepStatus = Field(
        default="pending",
        description="Execution status — set by executor, never by planner"
    )
    skip_reason: Optional[str] = Field(
        default=None,
        description="Populated if status=skipped, explaining why"
    )

    @field_validator("id")
    @classmethod
    def id_must_be_snake_case(cls, v: str) -> str:
        if " " in v:
            raise ValueError(f"PlanStep id must be snake_case, got: {v!r}")
        return v.lower()


class StepResult(BaseModel):
    """The result of executing a single PlanStep."""
    step_id: str = Field(description="ID of the plan step that was executed")
    raw_output: str = Field(
        description="Raw tool output — truncated to 4000 chars if longer"
    )
    status: ResultStatus = Field(
        description="confirmed | rejected | ambiguous"
    )
    finding: str = Field(
        description=(
            "1–4 sentence factual finding with specific observed values. "
            "Must reference actual numbers/states from the output."
        )
    )
    anomalies: Optional[str] = Field(
        default=None,
        description=(
            "Off-topic anomalies spotted during execution that may help the planner. "
            "Prefixed with NOTE: in the executor's output."
        )
    )


class StepResultSchema(BaseModel):
    """Structured output for the executor's result extraction step."""
    step_id: str = Field(description="ID of the plan step being reported")
    status: ResultStatus = Field(description="confirmed | rejected | ambiguous")
    finding: str = Field(
        description="1–4 sentence factual finding with specific observed values"
    )
    anomalies: Optional[str] = Field(
        default=None,
        description="Any off-topic anomalies spotted"
    )


# ---------------------------------------------------------------------------
# Planner structured output
# ---------------------------------------------------------------------------

class PlannerOutput(BaseModel):
    """
    Structured output schema for the Planner node.
    The reasoning model must always produce this exact schema.
    """
    reasoning: str = Field(
        description=(
            "Minimum 2 sentences. What does the current evidence tell you? "
            "Why are you making this next_action decision?"
        )
    )
    next_action: NextAction = Field(
        description="'execute' to continue, 'synthesize' to write the RCA"
    )
    hypotheses: list[Hypothesis] = Field(
        description="Complete updated list of all hypotheses with current statuses"
    )
    plan_steps: list[PlanStep] = Field(
        description=(
            "Complete updated list of ALL steps — pending, done, and skipped. "
            "The executor uses current_step_id to find its target step."
        )
    )
    current_step_id: str = Field(
        description=(
            "The step_id the executor should run next. "
            "Must be a step with status='pending' in plan_steps. "
            "Empty string if next_action='synthesize'."
        )
    )
    context_summary: Optional[str] = Field(
        default=None,
        description=(
            "Populated only on the first invocation (context gathering phase). "
            "Factual summary of topology, recent changes, known issues."
        )
    )
    replan_triggered: bool = Field(
        default=False,
        description=(
            "True if this invocation formed new hypotheses (increments replan_count). "
            "False if this is a normal plan review / step advancement."
        )
    )

    def to_state_patch(self) -> dict:
        """Convert structured output to a LangGraph state patch."""
        patch = {
            "next_action": self.next_action,
            "planner_reasoning": self.reasoning,
            "hypotheses": [h.model_dump() for h in self.hypotheses],
            "plan_steps": [s.model_dump() for s in self.plan_steps],
            "current_step_id": self.current_step_id,
        }
        if self.context_summary:
            patch["context_summary"] = self.context_summary
        return patch

    @field_validator("current_step_id")
    @classmethod
    def step_id_consistent_with_action(cls, v: str, info) -> str:
        action = info.data.get("next_action")
        if action == "execute" and not v:
            raise ValueError(
                "current_step_id must be non-empty when next_action='execute'"
            )
        return v


# ---------------------------------------------------------------------------
# Synthesizer structured output
# ---------------------------------------------------------------------------

class HypothesisEvaluated(BaseModel):
    hypothesis_id: str
    description: str
    status: HypothesisStatus
    evidence: str = Field(
        description="Specific step IDs and observed values supporting this status"
    )


class StepSummary(BaseModel):
    step_id: str
    finding: str = Field(description="One-line finding with key observed values")
    status: ResultStatus


class RCAOutput(BaseModel):
    """
    Structured output schema for the Synthesizer node.
    This is the final deliverable of the entire agent session.
    """
    replan_count: int = Field(
        default=0,
        description="Total number of times the investigation was replanned"
    )
    executive_summary: str = Field(
        description=(
            "One paragraph. What happened, what caused it, impact, resolution status. "
            "Written for the configured audience (technical or executive)."
        )
    )
    steps_executed: list[StepSummary] = Field(
        description="Ordered list of all steps run with one-line findings"
    )
    hypotheses_evaluated: list[HypothesisEvaluated] = Field(
        description="All hypotheses with final statuses and evidence"
    )
    root_cause: str = Field(
        description=(
            "Precise root cause statement referencing specific devices, interfaces, "
            "values, and evidence. Use 'Undetermined' if confidence=undetermined."
        )
    )
    confidence: Confidence = Field(
        description="Overall confidence level in the root cause determination"
    )
    confidence_reasoning: str = Field(
        description=(
            "Why this confidence level was assigned. "
            "Reference specific step IDs and evidence."
        )
    )
    proposed_solution: Optional[str] = Field(
        default=None,
        description="High-level solution description. None if confidence is too low."
    )
    remediation_steps: list[str] = Field(
        default_factory=list,
        description=(
            "Ordered, specific, actionable remediation steps. "
            "Steps touching live traffic are prefixed with [CHANGE REQUIRED]."
        )
    )
    contributing_factors: list[str] = Field(
        default_factory=list,
        description="Secondary factors that worsened impact or made diagnosis harder"
    )
    gaps_and_open_questions: list[str] = Field(
        description=(
            "Everything that could NOT be verified. Must be populated even if "
            "confidence=high. Use ['No significant gaps identified.'] if truly none."
        )
    )
    follow_up_investigations: list[str] = Field(
        default_factory=list,
        description="Post-incident tasks: monitoring improvements, config reviews, docs"
    )


# ---------------------------------------------------------------------------
# Aliases for tests / consistent naming
# ---------------------------------------------------------------------------

HypothesisSchema = Hypothesis
PlanStepSchema = PlanStep
HypothesisEvaluation = HypothesisEvaluated


# ---------------------------------------------------------------------------
# Agent state — the shared object that flows through all nodes
# ---------------------------------------------------------------------------

class AgentState(dict):
    """
    LangGraph state for network_operator.

    Defined as a TypedDict-compatible dict so LangGraph can handle
    partial updates from each node (nodes return only the keys they change).

    Key design decisions:
    - messages uses add_messages reducer for proper append semantics
    - step_results and plan_steps are replaced wholesale by each node
      (nodes return the complete updated list, not a delta)
    - findings_summary is replaced by the compressor each cycle
    """

    # Declared as class annotations for LangGraph's type inspection
    # Input
    problem_statement: str

    # Context phase output
    context_summary: str

    # Planning artefacts
    hypotheses: list[dict]          # serialised Hypothesis objects
    plan_steps: list[dict]          # serialised PlanStep objects
    current_step_id: str
    replan_count: int
    next_action: NextAction
    planner_reasoning: str

    # Execution artefacts — add_messages gives append semantics
    messages: Annotated[list[BaseMessage], add_messages]
    step_results: list[dict]        # serialised StepResult objects

    # Compressor output
    findings_summary: str

    # Final output
    rca: Optional[str]
    proposed_solution: Optional[str]
    confidence: Optional[Confidence]


def initial_state(problem_statement: str) -> dict:
    """
    Build a clean initial state for a new diagnostic session.
    Only problem_statement is required — everything else is empty/default.
    """
    return {
        "problem_statement": problem_statement,
        "context_summary": "",
        "hypotheses": [],
        "plan_steps": [],
        "current_step_id": "",
        "replan_count": 0,
        "next_action": "execute",
        "planner_reasoning": "",
        "messages": [],
        "step_results": [],
        "findings_summary": "",
        "rca": None,
        "proposed_solution": None,
        "confidence": None,
    }


# ---------------------------------------------------------------------------
# State helper utilities
# ---------------------------------------------------------------------------

def count_completed_steps(state: dict) -> int:
    """Return the number of steps with status='done' or 'skipped'."""
    return sum(
        1 for s in state.get("plan_steps", [])
        if s.get("status") in ("done", "skipped")
    )

def get_current_step(state: dict) -> Optional[PlanStep]:
    """Return the PlanStep matching current_step_id, or None."""
    step_id = state.get("current_step_id", "")
    for step_dict in state.get("plan_steps", []):
        if step_dict.get("id") == step_id:
            return PlanStep(**step_dict)
    return None


def get_pending_steps(state: dict) -> list[PlanStep]:
    """Return all steps with status='pending'."""
    return [
        PlanStep(**s)
        for s in state.get("plan_steps", [])
        if s.get("status") == "pending"
    ]


def get_step_results_for_step(state: dict, step_id: str) -> list[StepResult]:
    """Return all StepResults for a given step_id."""
    return [
        StepResult(**r)
        for r in state.get("step_results", [])
        if r.get("step_id") == step_id
    ]


def mark_step_done(state: dict, step_id: str) -> list[dict]:
    """Return updated plan_steps list with given step marked done."""
    return [
        {**s, "status": "done"} if s["id"] == step_id else s
        for s in state.get("plan_steps", [])
    ]


def mark_step_skipped(state: dict, step_id: str, reason: str) -> list[dict]:
    """Return updated plan_steps list with given step marked skipped."""
    return [
        {**s, "status": "skipped", "skip_reason": reason}
        if s["id"] == step_id else s
        for s in state.get("plan_steps", [])
    ]


def all_steps_resolved(state: dict) -> bool:
    """True if no pending steps remain."""
    return len(get_pending_steps(state)) == 0


def format_step_results_for_compressor(state: dict) -> str:
    """
    Format step results into a clean text block for the compressor prompt.
    Truncates raw_output to keep the prompt manageable.
    """
    results = state.get("step_results", [])
    if not results:
        return "No step results yet."

    lines = []
    for r in results:
        lines.append(
            f"[{r['step_id']}] status={r['status']}\n"
            f"  finding: {r['finding']}\n"
            f"  anomalies: {r.get('anomalies') or 'none'}"
        )
    return "\n\n".join(lines)


def format_plan_for_prompt(state: dict) -> str:
    """
    Format the current plan into a readable text block for the planner prompt.
    Shows all steps with their current statuses.
    """
    steps = state.get("plan_steps", [])
    if not steps:
        return "No plan steps yet."

    lines = []
    for s in steps:
        mark = {"pending": "[ ]", "done": "[✓]", "skipped": "[~]"}.get(
            s.get("status", "pending"), "[ ]"
        )
        destructive = " ⚠ DESTRUCTIVE" if s.get("destructive") else ""
        lines.append(
            f"{mark} {s['id']} ({s.get('tool_category', '?')} → {s.get('target_host', '?')}){destructive}\n"
            f"     hypothesis: {s.get('hypothesis_id', '?')}\n"
            f"     action: {s.get('command_hint', '?')}\n"
            f"     expected: {s.get('expected_result', '?')}"
        )
        if s.get("skip_reason"):
            lines[-1] += f"\n     skipped because: {s['skip_reason']}"

    return "\n\n".join(lines)


def format_hypotheses_for_prompt(state: dict) -> str:
    """Format hypotheses with statuses for use in prompts."""
    hyps = state.get("hypotheses", [])
    if not hyps:
        return "No hypotheses formed yet."

    lines = []
    for h in hyps:
        status_icon = {
            "pending": "?",
            "confirmed": "✓",
            "rejected": "✗",
            "ambiguous": "~",
        }.get(h.get("status", "pending"), "?")
        lines.append(
            f"[{status_icon}] {h['id']}: {h['description']}"
        )
        if h.get("evidence"):
            lines.append(f"    evidence: {h['evidence']}")
    return "\n".join(lines)
