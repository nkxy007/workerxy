from subagents.prompts import AUTOMATA_AGENT_PROMPT

# Tools are injected from tools_helpers/automata_tools.py in net_deepagent.py.
# The AutomataManager reference is wired into those tools at startup via
# set_automata_manager() called in net_deepagent_cli/loop.py.

automata_agent = {
    "name": "automata_agent",
    "description": (
        "Use this subagent for any scheduling or recurring task management requests. "
        "Examples: creating a background job to ping a host every N minutes, "
        "listing or stopping scheduled jobs, and reading job execution logs to verify results. "
        "Delegate here whenever a ticket or user asks for a periodic, scheduled, or repeating action."
    ),
    "system_prompt": AUTOMATA_AGENT_PROMPT,
    "tools": [],  # Injected in net_deepagent.py from tools_helpers/automata_tools.py
}
