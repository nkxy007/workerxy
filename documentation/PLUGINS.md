# External Subagent Plugins

WorkerXY allows you to dynamically extend the agent's capabilities by adding third-party subagents without modifying the core source code. These agents are defined declaratively using JSON files.

---

## 📁 Directory Structure

Custom subagents must be placed in their own subdirectory under:
`~/.net-deepagent/net-agent/subagents/`

```text
~/.net-deepagent/net-agent/subagents/
└── <agent-name>/
    └── agent.json
```

---

## 📄 `agent.json` Schema

The `agent.json` file defines the identity, logic, and tools available to the subagent.

```json
{
  "name": "my_custom_agent",
  "description": "Handles specialist tasks for X...",
  "system_prompt": "You are a specialist in X. Use provided tools to Y.",
  "tool_filter": {
    "prefixes": ["net_", "sn_"],
    "names": ["search_internet"],
    "categories": ["lan", "cloud"]
  },
  "include_tools": ["search_internet", "user_clarification_and_action_tool"],
  "skills": [
    "~/.net-deepagent/net-agent/skills/my-specialist-skill"
  ],
  "model": "gpt-5-mini",
  "enabled": true
}
```

### Configuration Fields

| Field | Required | Description |
| :--- | :--- | :--- |
| `name` | ✅ | Unique identifier for the agent (snake_case). |
| `description` | ✅ | High-level description used by the main agent for routing. |
| `system_prompt` | ✅ | The core instructions for the subagent LLM. |
| `tool_filter.prefixes` | ❌ | Automatically include MCP tools starting with these prefixes (e.g., `net_`). |
| `tool_filter.names` | ❌ | Exact names of MCP tools to include. |
| `tool_filter.categories` | ❌ | Predefined categories: `cloud`, `lan`, `design`, `datacenter`, `isp`, `lab`, `servicenow`, `jira`. |
| `include_tools` | ❌ | Include core built-in tools: `search_internet`, `user_clarification_and_action_tool`. |
| `skills` | ❌ | List of absolute paths (supports `~`) to skill directories. Must contain a `SKILL.md`. |
| `model` | ❌ | LLM model key from `AVAILABLE_MODELS` (default: `gpt-5-mini`). |
| `enabled` | ❌ | Set to `false` to disable the agent without deleting it (default: `true`). |

---

## 🛠️ Usage Example: Weather Agent

1. Create the directory:
   ```bash
   mkdir -p ~/.net-deepagent/net-agent/subagents/weather_agent
   ```

2. Create `~/.net-deepagent/net-agent/subagents/weather_agent/agent.json`:
   ```json
   {
     "name": "weather_agent",
     "description": "Specialist for weather reports and environmental conditions.",
     "system_prompt": "You are a meteorologist. Use tools to provide accurate weather data.",
     "tool_filter": {
       "prefixes": ["weather_"]
     },
     "include_tools": ["search_internet"],
     "enabled": true
   }
   ```

3. Restart WorkerXY. You should see a log entry confirming the load:
   `INFO: Loaded 1 third-party plugin subagent(s)`

---

## 🧪 Verification

To ensure your plugin is working correctly, you can run the subagent tests:
```bash
conda run -n test_langchain_env pytest tests/test_third_party_subagent_loader.py -v
```
