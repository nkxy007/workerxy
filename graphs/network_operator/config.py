"""
config.py
---------
All runtime constants and model configuration for network_operator.

Every value here can be overridden at graph invocation time via RunnableConfig:

    graph.invoke(
        {"problem_statement": "..."},
        config={"configurable": {"max_replans": 5, "reasoning_model": "openai/o3"}}
    )
"""

from dataclasses import dataclass, field
from typing import Optional
from langchain_core.runnables import RunnableConfig


# ---------------------------------------------------------------------------
# Model identifiers
# ---------------------------------------------------------------------------

# Reasoning model — used by the Planner.
# Must support structured output and extended/chain-of-thought reasoning.
# Supported values (examples):
#   "anthropic/claude-3-7-sonnet-latest"   ← default, best balance
#   "openai/o3"
#   "openai/o4-mini"
#   "google_vertexai/gemini-2.0-flash-thinking-exp"
REASONING_MODEL: str = "claude-sonnet-4-5-20250929"

# Fast execution model — used by Executor and Compressor.
# Must support tool calling. Optimise for speed and cost.
EXECUTION_MODEL: str = "claude-haiku-4-5-20251001"

# Quality synthesis model — used by Synthesizer.
# Must produce polished long-form prose with structured output.
SYNTHESIS_MODEL: str = "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# Agent behaviour limits
# ---------------------------------------------------------------------------

# Maximum number of times the planner can form entirely new hypotheses.
# Each replan increments replan_count. When this is reached the agent
# must hand off to the synthesizer regardless of confidence.
MAX_REPLANS: int = 3

# Maximum total plan steps across the entire session (including replans).
# Prevents runaway planning on ambiguous problems.
MAX_STEPS: int = 20

# Maximum tool calls the executor may make within a single step.
# Prevents the executor from going rogue on a single diagnostic step.
MAX_TOOL_CALLS_PER_STEP: int = 8

# Maximum schema validation retries for planner structured output.
PLANNER_VALIDATION_RETRIES: int = 3

# Maximum words in the compressor findings_summary output.
# Keeps planner context clean across cycles.
COMPRESSOR_MAX_WORDS: int = 350


# ---------------------------------------------------------------------------
# Model temperature settings
# ---------------------------------------------------------------------------

# Reasoning models (claude-3-7, o3, etc.) typically require temperature=1.
REASONING_TEMPERATURE: float = 1.0

# Execution and synthesis models benefit from lower temperature for consistency.
EXECUTION_TEMPERATURE: float = 0.0
SYNTHESIS_TEMPERATURE: float = 0.2


# ---------------------------------------------------------------------------
# Configurable dataclass — passed through RunnableConfig
# ---------------------------------------------------------------------------

@dataclass
class NetworkOperatorConfig:
    """
    Runtime configuration for the network_operator graph.

    Usage:
        from langgraph.types import RunnableConfig
        config = NetworkOperatorConfig(max_replans=5, reasoning_model="openai/o3")
        graph.invoke(state, config={"configurable": config.as_dict()})
    """

    reasoning_model: str = REASONING_MODEL
    execution_model: str = EXECUTION_MODEL
    synthesis_model: str = SYNTHESIS_MODEL

    planner_thinking_budget: int = 0
    planner_temperature: float = REASONING_TEMPERATURE
    execution_temperature: float = EXECUTION_TEMPERATURE
    synthesis_temperature: float = SYNTHESIS_TEMPERATURE

    max_replans: int = MAX_REPLANS
    max_steps: int = MAX_STEPS
    max_tool_calls_per_step: int = MAX_TOOL_CALLS_PER_STEP
    planner_validation_retries: int = PLANNER_VALIDATION_RETRIES
    compressor_max_words: int = COMPRESSOR_MAX_WORDS

    # Optional deployment context injected into prompts
    org_name: Optional[str] = None
    platform_hints: Optional[str] = None
    rca_audience: str = "technical"          # "technical" | "executive"
    include_remediation: bool = True

    # Extra standing instructions per node (appended to base system prompts)
    extra_planner_context: Optional[str] = None
    extra_executor_context: Optional[str] = None
    extra_synthesizer_context: Optional[str] = None

    def as_dict(self) -> dict:
        return {
            k: v for k, v in self.__dict__.items()
            if v is not None or k in (
                "org_name", "platform_hints",
                "extra_planner_context",
                "extra_executor_context",
                "extra_synthesizer_context",
            )
        }


def get_config(runnable_config: RunnableConfig) -> NetworkOperatorConfig:
    """
    Extract NetworkOperatorConfig from a LangGraph RunnableConfig.
    Falls back to defaults for any missing keys.
    """
    configurable = runnable_config.get("configurable", {})
    valid_fields = NetworkOperatorConfig.__dataclass_fields__.keys()
    filtered = {k: v for k, v in configurable.items() if k in valid_fields}
    return NetworkOperatorConfig(**filtered)


DEFAULT_CONFIG = NetworkOperatorConfig()
