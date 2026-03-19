from typing import List, Dict, Any, Optional
from langchain_core.tools import tool
from subagents.prompts import SERVICE_DESK_PROMPT

# The tools for this agent are provided by the net_lab_mcp_server and injected in net_deepagent.py
# We don't need to define Langchain tools here, just the agent definition
# that the framework will use to route to it.

service_desk_agent = {
    "name": "service_desk_agent",
    "description": (
        "Use this subagent for IT service management (ITSM) tasks such as monitoring or querying "
        "ServiceNow incidents and independently creating or managing change requests."
    ),
    "system_prompt": SERVICE_DESK_PROMPT,
    "tools": [],  # Tools are injected or handled by the MCP client mechanism in net_deepagent.py
}
