from typing import List, Dict, Any, Optional
from subagents.prompts import TICKET_SCOUT_PROMPT

# The tools for this agent are provided by the network MCP server and injected in net_deepagent.py
# We don't need to define Langchain tools here, just the agent definition
# that the framework will use to route to it.

ticket_scout_agent = {
    "name": "ticket_scout_agent",
    "description": (
        "Use this subagent for Jira ticket management tasks such as fetching ticket details, getting work and tasks to do, "
        "updating fields, adding comments, transitioning statuses, and searching for tickets using JQL."
    ),
    "system_prompt": TICKET_SCOUT_PROMPT,
    "tools": [],  # Tools are injected or handled by the MCP client mechanism in net_deepagent.py
}
