# CoworkerX Networking — CLI Features

A living reference of the features supported by the `net_deepagent_cli`.

---

## 🤖 Agent Core

| Feature | Command / Detail |
|---|---|
| Interactive chat with the main agent | Type any message at the `>` prompt |
| Streaming responses | Agent responses stream token-by-token in real-time |
| Tool execution visibility | Each tool call is displayed with name and arguments |
| Security approval for sensitive tools | Prompted before `execute_shell_command`, `execute_generated_code`, etc. |
| Human-in-the-loop clarification | Agent can ask user questions via `user_clarification_and_action_tool` |
| Auto-approve mode | `--auto-approve` CLI flag bypasses approval prompts |

---

## 🔌 A2A Agent Management (`/agents`)

Dynamically attach external Agent-to-Agent (A2A) specialist agents at runtime.

| Command | Description |
|---|---|
| `/agents` or `/agents list` | Show all agents in the registry with session loaded/unloaded status |
| `/agents add <name> <url>` | Persist agent to `agents_registry.json` and load it live |
| `/agents remove <name>` | Remove agent from registry **and** unload from session |
| `/agents unload <name>` | Unload from session only — registry entry kept for later |
| `/agents load` | Reload all registry agents into the current session |

**Built-in A2A agents:**
- `dns_deepagent` — DNS resolution and diagnostics
- `dhcp_deepagent` — DHCP lease/pool management and troubleshooting

---

## 🧠 Memory

| Feature | Command / Detail |
|---|---|
| Persistent agent memory | Stored at `~/.net-deepagent/<agent-name>/agent.md` |
| Memory injected at each turn | Automatically prepended to system prompt |
| View current memory | `/memory` |

---

## 🛠 Skills

| Feature | Command / Detail |
|---|---|
| List available skills | `/skills` or `/skills list` |
| Extract skill from document | `/skills add <path>` or `/skills extract <path>` |
| Auto-injected into system prompt | Skills discovered from `~/.net-deepagent/<name>/skills/` and `./skills/` |

---

## 💾 Session Management

| Feature | Command / Detail |
|---|---|
| Save conversation to file | `/save <name>` |
| Resume saved session | `/resume <name>` |
| List all saved sessions | `/sessions` |
| Start a new session | `/session new` — Prompt to save current session then clear it fresh |
| Delete a saved session | `/session delete <name>` — Delete a saved session file |
| Adjust drift sensitivity | `/session threshold <val>` — Set topic drift threshold (0.0-1.0) |
| Automatic context detection | `--automatic-context-detection` (startup flag) |
| Persistent prompt history | Stored at `~/.net-deepagent/<name>/history` |

---

## ⚙️ Automata (Background Tasks)

Scheduled tasks that run autonomously in the background while you continue chatting.

| Command | Description |
|---|---|
| `/automata` | Open the automata management menu |
| `/automata list` | List all scheduled background tasks |
| `/automata add` | Schedule a new recurring task |
| `/automata remove <id>` | Remove a task by ID |
| `/automata resume <id>` | Resume a stale/paused task |
| `/automata logs <id>` | List execution logs for a task |
| `/automata view <filename>` | View a specific log file |

Logs are persisted to `~/.net-deepagent/<name>/automata_results/`.

---

## 📊 Context & Diagnostics

| Feature | Command / Detail |
|---|---|
| Token usage | `/tokens` — total tokens used this session |
| Context analysis | `/context` — breakdown by message type + estimated depth |
| Clear conversation | `/clear` |

---

## 🔧 MCP Tools (via MCP server)

The agent connects to an MCP server on startup and dynamically loads all registered tools. Examples include:

- LAN networking tools (routing, switching, SSH config)
- Cloud tools (AWS, Azure, GCP)
- Network design / Draw.io diagram tools
- Datacenter and ISP tools
- Retriever/Archiver tools (conversation memory, RAG queries)

---

## 🎨 UI & Autocompletion

| Feature | Detail |
|---|---|
| Rich terminal UI | Colours, panels, markdown rendering, progress spinners |
| Command autocompletion | Tab-complete for all `/commands` and their sub-commands |
| Partial match suggestions | Typing `/ag` suggests `/agents` |
| Sub-command hints | After `/agents ` tab shows `list`, `add`, `remove`, `unload`, `load` |
| Prompt history | Up/down arrows cycle through previous inputs |

---

### ⚡ Topic-Drift Detection (Experimental)

When started with `--automatic-context-detection`, the agent monitors your questions. If it detects a significant shift in topic (e.g., from BGP troubleshooting to AWS lambda functions), it will suggest starting a new session to keep the context clean.
