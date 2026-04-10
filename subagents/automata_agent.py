from subagents.prompts import AUTOMATA_AGENT_PROMPT

# Tools are injected from tools_helpers/automata_tools.py in net_deepagent.py.
# The AutomataManager reference is wired into those tools at startup via
# set_automata_manager() called in net_deepagent_cli/loop.py.

automata_agent = {
    "name": "automata_agent",
    "description": (
        "This agent deela mainly with scheduled actions locally, like cron jobs. "
        "Use this subagent for scheduling a once to run task or a recurring task on our agency"
        "Examples: creating a background job to ping a host every N minutes, "
        "It can perform listing jobs, stopping scheduled jobs or activities, and reading job execution logs to verify results. "
        "Delegate to this agent whenever a ticket, a task or user asks for a periodic, scheduled, or repeating actions handling."
    ),
    "system_prompt": AUTOMATA_AGENT_PROMPT,
    "tools": [],  # Injected in net_deepagent.py from tools_helpers/automata_tools.py
}
