from typing import List, Dict, Any, Optional
from langchain_core.tools import tool
from subagents.prompts import NET_LAB_AGENT_PROMPT

# The tools for this agent are provided by the net_lab_mcp_server.
# We don't need to define Langchain tools here, just the agent definition
# that the framework will use to route to it.

net_lab_agent = {
    "name": "net_lab_agent",
    "description": (
        "Use this subagent to create EVE-NG labs, deploy network topologies, "
        "and configure network devices using EVE-NG."
    ),
    "system_prompt": NET_LAB_AGENT_PROMPT,
    "tools": [],  # Tools are injected or handled by the MCP client mechanism
}
