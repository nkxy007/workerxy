# Network Operator Agent — Build Plan (v2)

## Overview

`network_operator` is a LangGraph agent modelled after a network engineer troubleshooting a live incident. It receives a problem statement, gathers context, forms hypotheses, executes diagnostic commands iteratively, replans when results don't confirm a hypothesis, and ultimately writes a Root Cause Analysis (RCA) with proposed remediation.

---

## Architecture

```
START → PLANNER ──► EXECUTOR ──► COMPRESSOR ──► PLANNER
                        │                           │
                    (tool loop)              next_action=synthesize
                        │                           │
                    TOOL NODE                       ▼
                                              SYNTHESIZER → END
```

The **Planner** is the sole decision-maker. After every execution cycle it reviews compressed findings and decides:
- `execute` — run the next step (or replan and run)
- `synthesize` — root cause confirmed (or MAX_REPLANS reached), hand off

This eliminates the Router entirely. Routing logic belonged in the reasoning model all along.

---

## Key Design Decisions vs v1

| v1 | v2 | Reason |
|----|----|--------|
| Separate Router node | Planner decides `next_action` | Router had fragile ID-based dependency tracking; planner reasons about completion more accurately |
| Raw tool output passed to planner | Compressor node summarises findings first | Prevents context bloat and reasoning degradation on replan 2+ |
| Planner hypothesises immediately | Context-gathering sub-phase first | Mirrors real engineer behaviour — read before guessing |
| `success: bool` | `status: confirmed / rejected / ambiguous` | Binary forced wrong routing decisions on partial results |
| Schema validation absent | Validation retry loop on planner output | Reasoning models produce invalid JSON under pressure |
| No destructive action gate | `destructive: bool` flag + human-in-the-loop interrupt | Shell/SSH/code execution tools can cause outages |

---

## State Schema

```python
from typing import Annotated, TypedDict, Literal
from langgraph.graph.message import add_messages

class StepResult(TypedDict):
    step_id: str
    output: str                                    # raw tool output (pre-compression)
    status: Literal["confirmed", "rejected", "ambiguous"]
    finding: str                                   # one-sentence human-readable finding

class PlanStep(TypedDict):
    id: str                                        # semantic label e.g. "check_bgp_timers"
    hypothesis_id: str
    description: str
    target_host: str                               # explicit — executor must not guess
    tool_category: Literal["ssh", "shell", "file_read", "search", "code_exec"]
    command_hint: str                              # planner specifies intent, executor picks exact command
    expected_result: str
    destructive: bool                              # triggers human-in-the-loop if True
    status: Literal["pending", "done", "skipped"]

class Hypothesis(TypedDict):
    id: str
    description: str
    status: Literal["pending", "confirmed", "rejected", "ambiguous"]

class AgentState(TypedDict):
    # Input
    problem_statement: str

    # Context gathered before first plan
    context_summary: str                           # topology, changelogs, configs

    # Planning artefacts
    hypotheses: list[Hypothesis]
    plan_steps: list[PlanStep]
    current_step_id: str                           # semantic label, not index
    replan_count: int
    next_action: Literal["execute", "synthesize"]
    planner_reasoning: str                         # why planner made its decision (observability)

    # Execution artefacts
    messages: Annotated[list, add_messages]
    step_results: list[StepResult]

    # Compressed findings passed to planner on each cycle
    findings_summary: str

    # Final output
    rca: str | None
    proposed_solution: str | None
    confidence: Literal["high", "medium", "low", "undetermined"] | None
```

---

## Node Definitions

### 1. Planner Node

**Purpose:** On every invocation, reason about the current state and either produce/revise a plan or declare completion. This is the brain of the agent.

**Model:** Reasoning-capable model via `init_chat_model` — configurable at runtime.

```python
from langchain.chat_models import init_chat_model

reasoning_model = init_chat_model(
    model="anthropic/claude-3-7-sonnet-latest",
    model_provider="anthropic",
    temperature=1,
)
```

**Three invocation modes — all handled by the same node:**

**Mode 1 — First call (no context yet):**
- Use `search_internet` and `file_read` tools to gather topology docs, recent changelogs, device configs, known issues
- Produce `context_summary`
- Form initial `hypotheses` ranked by likelihood
- Produce `plan_steps` with full specificity (host, tool category, command hint, expected result, destructive flag)
- Set `next_action = "execute"`

**Mode 2 — Replan call (step results available):**
- Read `findings_summary` (compressed, not raw output)
- Update hypothesis statuses
- Decide: are remaining steps still valid given what we learned?
- If yes: adjust plan, set `next_action = "execute"`
- If no valid path remains and `replan_count < MAX_REPLANS`: form new hypotheses, new steps, set `next_action = "execute"`, increment `replan_count`
- If root cause confirmed or `replan_count >= MAX_REPLANS`: set `next_action = "synthesize"`

**Mode 3 — Completion check:**
- After all steps done, planner reviews whether the question is actually answered
- Can push to synthesize even with remaining steps if hypothesis is conclusively confirmed
- Can add final validation steps if evidence is ambiguous

**Structured output schema (enforced via `with_structured_output`):**

```python
class PlannerOutput(BaseModel):
    reasoning: str                    # mandatory — explains the decision
    next_action: Literal["execute", "synthesize"]
    hypotheses: list[Hypothesis]
    plan_steps: list[PlanStep]        # full updated list
    current_step_id: str
    context_summary: str | None       # only on first call
```

Using `with_structured_output` eliminates manual JSON parsing and handles retry on schema failure automatically.

```python
structured_planner = reasoning_model.with_structured_output(
    PlannerOutput,
    include_raw=True    # lets us inspect raw response if validation fails
)
```

**Validation retry loop:**

```python
def planner_node(state: AgentState) -> AgentState:
    for attempt in range(3):
        try:
            prompt = build_planner_prompt(state)
            result = structured_planner.invoke(prompt)
            break
        except ValidationError as e:
            if attempt == 2:
                raise  # surface after 3 attempts
            state["messages"].append(SystemMessage(f"Output schema invalid: {e}. Try again."))

    return {**state, **result.dict()}
```

**System prompt:**
```
You are a senior network engineer and the decision-maker of this diagnostic session.

On each invocation you must:
1. Review the problem statement and any findings so far
2. Update hypothesis statuses based on evidence
3. Decide explicitly: should we keep executing or do we have enough to write the RCA?
4. If executing: specify the next step with full detail (host, tool, expected result)
5. If done: set next_action=synthesize

You must always populate the `reasoning` field explaining your decision.
Mark any step that could cause disruption as destructive=true and only skip authorization if you had a prior authorization like a yolo mode or some flag we will figure out.
Prefer commands that falsify hypotheses fastest. Do not repeat steps already done.
```

---

### 2. Executor Node

**Purpose:** Execute exactly the step the planner specified, using the appropriate tool, and record the result honestly.

**Model:** Fast non-reasoning model — no strategising, just execution and honest result recording.

```python
execution_model = init_chat_model(
    model="anthropic/claude-haiku-4-5",
    model_provider="anthropic",
)
```

**Available tools:**
- `ssh_command(host: str, command: str) -> str` — run command on remote device
- `shell_command(command: str) -> str` — local shell execution
- `read_file(path: str) -> str` — read config, log, or topology file
- `write_file(path: str, content: str) -> str` — edit config file
- `search_internet(query: str) -> str` — look up vendor docs, CVEs, known issues
- `execute_code(language: str, code: str) -> str` — run analysis scripts

**Human-in-the-loop gate for destructive steps:**

```python
from langgraph.types import interrupt

def executor_node(state: AgentState) -> AgentState:
    step = get_current_step(state)

    if step["destructive"]:
        confirmation = interrupt({
            "message": f"Step '{step['id']}' is destructive: {step['description']}. Approve?",
            "step": step,
        })
        if not confirmation.get("approved"):
            # Mark skipped, let planner decide what to do next
            return mark_step_skipped(state, step["id"], reason="user rejected destructive action")

    # Execute
    messages = state["messages"] + [HumanMessage(content=format_step_for_executor(step))]
    response = executor_with_tools.invoke(messages)
    result = parse_execution_result(response, step)

    return {
        **state,
        "messages": messages + [response],
        "step_results": state["step_results"] + [result],
    }
```

**Executor system prompt:**
```
You are executing a specific diagnostic step on a network device.
Step details will be provided. Call the appropriate tool as specified.
After receiving the tool result, compare it honestly against the expected result.
Report status as: confirmed (matches expected), rejected (clearly contradicts hypothesis),
or ambiguous (partial match, inconclusive, or unexpected output).
Do not interpret beyond what the data shows. Record the raw finding concisely.
```

The executor uses `ToolNode` for automatic tool dispatch and runs in a ReAct sub-loop until it has a final `StepResult` to record.

---

### 3. Compressor Node

**Purpose:** Between executor and planner, distill raw tool output into a structured findings summary. Keeps planner context clean across replans.

**Model:** Same fast model as executor — this is a summarisation task.

```python
def compressor_node(state: AgentState) -> AgentState:
    if not state["step_results"]:
        return state

    prompt = f"""
    Summarise the following diagnostic findings into a concise structured report.
    For each step: what was checked, what was found, what hypothesis it supports or refutes.
    Be factual. Do not add interpretation beyond what the data shows.
    Do not include raw command output — only findings.

    Step results:
    {format_step_results(state["step_results"])}

    Previous summary (if any):
    {state.get("findings_summary", "None")}
    """

    response = fast_model.invoke(prompt)
    return {**state, "findings_summary": response.content}
```

This node has no tools and no branching — it always runs between executor and planner.

---

### 4. Synthesizer Node

**Purpose:** Write the final RCA. Confidence-aware — explicitly flags gaps and unvalidated hypotheses.

**Model:** High-quality instruction-following model.

**Output structure (enforced):**

```python
class RCAOutput(BaseModel):
    executive_summary: str
    steps_executed: list[dict]          # step_id + one-line finding
    hypotheses_evaluated: list[dict]    # hypothesis + status + evidence
    root_cause: str                     # or "Undetermined" if confidence=low
    confidence: Literal["high", "medium", "low", "undetermined"]
    confidence_reasoning: str           # why this confidence level
    proposed_solution: str | None
    remediation_steps: list[str]
    gaps_and_open_questions: list[str]  # explicitly what we couldn't validate
    follow_up_investigations: list[str]
```

```python
def synthesizer_node(state: AgentState) -> AgentState:
    prompt = build_synthesis_prompt(state)
    result = synthesis_model.with_structured_output(RCAOutput).invoke(prompt)
    return {
        **state,
        "rca": format_rca(result),
        "proposed_solution": result.proposed_solution,
        "confidence": result.confidence,
    }
```

---

## Graph Assembly

```python
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

builder = StateGraph(AgentState)

builder.add_node("planner",     planner_node)
builder.add_node("executor",    executor_node)
builder.add_node("tools",       ToolNode(tools))
builder.add_node("compressor",  compressor_node)
builder.add_node("synthesizer", synthesizer_node)

builder.set_entry_point("planner")

# Planner → executor or synthesizer based on next_action
builder.add_conditional_edges(
    "planner",
    lambda state: state["next_action"],
    {
        "execute":    "executor",
        "synthesize": "synthesizer",
    }
)

# Executor → tools if tool call pending, else compressor
builder.add_conditional_edges(
    "executor",
    should_call_tools,
    {
        "tools":      "tools",
        "compressor": "compressor",
    }
)

# Tools always return to executor
builder.add_edge("tools", "executor")

# Compressor always returns to planner
builder.add_edge("compressor", "planner")

builder.add_edge("synthesizer", END)

graph = builder.compile(
    interrupt_before=["executor"],   # allows destructive step gate to work
    checkpointer=MemorySaver(),      # enables resumption after human approval
)
```

---

## Configuration

```python
# config.py
MAX_REPLANS       = 3
MAX_TOOL_CALLS    = 15   # per executor invocation
REASONING_MODEL   = "anthropic/claude-3-7-sonnet-latest"
EXECUTION_MODEL   = "anthropic/claude-haiku-4-5"
SYNTHESIS_MODEL   = "anthropic/claude-3-5-sonnet-latest"
```

All injectable via `RunnableConfig` — no code changes needed to swap models.

---

## File & Module Structure

```
network_operator/
├── agent.py                # graph assembly and compile
├── state.py                # AgentState, PlanStep, Hypothesis, StepResult TypedDicts
├── nodes/
│   ├── planner.py          # planner_node, PlannerOutput schema, prompt builder
│   ├── executor.py         # executor_node, destructive gate, step formatter
│   ├── compressor.py       # compressor_node, findings summariser
│   └── synthesizer.py      # synthesizer_node, RCAOutput schema, RCA formatter
├── tools/                  # from MCP this is just a reresentation of the tools
│   ├── __init__.py         # tool registry
│   ├── ssh.py              # ssh_command
│   ├── shell.py            # shell_command
│   ├── files.py            # read_file, write_file
│   ├── search.py           # search_internet
│   └── code_exec.py        # execute_code
├── prompts/                # this is in prompts.py
│   ├── planner.txt
│   ├── executor.txt
│   └── synthesizer.txt
├── config.py
└── tests/
    ├── test_planner.py      # unit: structured output, replan logic, completion detection
    ├── test_executor.py     # unit: tool selection, ambiguous result handling, destructive gate
    ├── test_compressor.py   # unit: summary quality, context size reduction
    ├── test_synthesizer.py  # unit: confidence scoring, gap reporting
    └── test_graph.py        # e2e: scenario runs with mock tools
```

---

## Example Flow

**Input:** `"BGP session between core-router-1 and isp-peer-2 keeps flapping every ~4 minutes"`

**Cycle 1 — Context Gathering + Planning:**
- Planner reads topology file → finds core-router-1 peers with isp-peer-2 over ge-0/0/2
- Planner searches for recent changes → finds MTU change ticket 3 days ago
- Hypotheses formed: H1 MTU mismatch (high likelihood given recent change), H2 CPU spike, H3 ISP policy change
- Plan: check interface counters → check MTU both sides → check CPU → pull BGP logs
- `next_action = "execute"`

**Cycle 1 — Execution:**
- `ssh_command(core-router-1, "show interfaces ge-0/0/2")` → giant frame drops: 4,821 in last hour
- `status = "confirmed"` for H1

**Cycle 1 — Compression:**
- Findings summary: "ge-0/0/2 on core-router-1 shows 4,821 giant frame drops in the last hour, consistent with MTU mismatch. H1 (MTU mismatch) supported."

**Cycle 2 — Planner reviews:**
- H1 confirmed with strong evidence
- Remaining steps (CPU, BGP logs) no longer needed to confirm root cause
- `reasoning = "Giant frame drops on the peering interface directly explain BGP keepalive drops. MTU mismatch confirmed. No need to continue."`
- `next_action = "synthesize"`

**Synthesizer output:**
- Root cause: MTU mismatch on ge-0/0/2 (router 9000, ISP 1500, PMTUD blocked)
- Confidence: high
- Solution: set `ip tcp adjust-mss 1452` on peering interface or align MTU with ISP
- Gaps: ISP-side MTU not directly verified (read-only access)

---

## Testing Strategy

- **Planner unit tests:** mock findings, assert correct `next_action`, assert schema always valid, assert `reasoning` always populated
- **Executor unit tests:** mock tools, assert correct tool called for each `tool_category`, assert ambiguous handling, assert destructive gate fires
- **Compressor unit tests:** assert output is shorter than input, assert all step IDs referenced, assert no raw command output bleeds through
- **Synthesizer unit tests:** assert confidence matches evidence quality, assert gaps section populated when hypotheses unresolved
- **Graph e2e scenarios:**
  - Happy path: H1 confirmed in one cycle → synthesize
  - Replan path: H1 rejected, H2 confirmed in second cycle
  - Max replan: all hypotheses rejected → synthesize with `confidence=undetermined`
  - Destructive gate: step with `destructive=true` → interrupt fires → user rejects → planner replans without that step