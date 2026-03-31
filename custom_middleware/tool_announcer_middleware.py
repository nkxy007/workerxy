"""
Tool Announcer Middleware
Runs after each model turn. If the model decided to call a tool, prints
a human-readable announcement derived from TOOL_NAME_MAP.

Design notes:
- Wrapped in try/except so a failure here never surfaces as an agent error.
- Uses dict.get() (not dict[key]) throughout for safe lookup.
"""
import logging
from langchain.agents.middleware import after_model, AgentState
from langgraph.runtime import Runtime
from langchain_core.messages import AIMessage
from custom_middleware.tools_name_mapper import TOOL_NAME_MAP

logger = logging.getLogger(__name__)


@after_model
def announce_tool_call(state: AgentState, runtime: Runtime) -> dict | None:
    """Print a friendly label whenever the model decides to invoke a known tool."""
    try:
        messages = state.get("messages", [])
        if not messages:
            logger.warning("No messages in state")
            return None

        last_msg = messages[-1]
        if not isinstance(last_msg, AIMessage):
            logger.warning("Last message is not an AIMessage")
            return None

        tool_calls = getattr(last_msg, "tool_calls", None) or []
        if not tool_calls:
            logger.debug("No tool calls in last message")
            return None

        for tc in tool_calls:
            name = tc.get("name", "")
            args = tc.get("args", {})

            # Special handling for the 'task' tool (subagent spawner)
            if name == "task":
                subagent_type = args.get("subagent_type", "unknown")
                task_desc = args.get("description", "no description")
                # Truncate long descriptions for cleaner console output
                if len(task_desc) > 80:
                    task_desc = task_desc[:77] + "..."
                print(f"\U0001f527 Agent action \u2192 Spawning {subagent_type} subagent to: {task_desc}")
                continue

            label = TOOL_NAME_MAP.get(name)
            if label:
                print(f"\U0001f527 Agent action \u2192 {label}")
            else:
                logger.debug(f"Tool call not found in TOOL_NAME_MAP: {name}")

    except Exception as exc:  # noqa: BLE001
        logger.warning("announce_tool_call middleware failed (non-fatal): %s", exc)

    return None
