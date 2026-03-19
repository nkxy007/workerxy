# 🤖 WorkerXY

**The Ultimate AI Copilot for Network Operations & Automation.**

WorkerXY is a high-performance, agentic AI system designed to streamline network diagnostics, cloud management, and datacenter operations. From troubleshooting BGP drifts to managing global AWS clusters, WorkerXY is your specialist operational companion.

---

## 🌟 Core Features

### 🤖 Intelligent Agent Core
*   **Agent-to-Agent (A2A)**: Dynamically attach specialist agents at runtime via `/agents`.
*   **Streaming TUI**: Real-time token-streaming cockpit with rich formatting.
*   **Security Guardrails**: Mandatory approval for sensitive ops like shell/code execution.

### 🧠 Persistent Memory & Skills
*   **Long-term Memory**: Remembers past interactions across sessions.
*   **Dynamic Skills**: Extract new capabilities from documentation instantly via `/skills add <path>`.
*   **Auto-Learning**: Updates skills based on session context.

### ⚙️ Automata (Autonomous Ops)
*   **Background Scheduling**: Schedule recurring tasks like "verify server status every 15 mins".
*   **Autonomous Execution**: WorkerXY handles the execution and logging even while you're offline.
*   **Full Lifecycle**: List, pause, resume, and inspect detailed execution logs via `/automata`.

### 🛡️ Smart Middlewares
*   **NetPII Pseudonymization**: Automatically masks IPs, MACs, and URLs for privacy.
*   **Context Pruning**: Intelligent summarization as you approach token limits (85% threshold).
*   **Input Protection**: Integrated guardrails to prevent prompt injections.

---

## 🎨 User Interfaces

### 🏎️ Agent Cockpit (CLI)
A high-performance terminal UI designed for operational awareness.
- **Unified View**: Chat history, live tool execution, and logs in one place.
- **Autocomplete**: Full tab-autocompletion for all Slash-commands.

### 🌐 WorkerXY Dashboard (Streamlit)
- **Visual Logs**: Watch tool execution and agent thoughts in real-time.
- **Hot-Configuration**: Reload middlewares and settings without restarting.

---

## 🔧 Deep Tool Integrations

WorkerXY leverages the **Model Context Protocol (MCP)** to interact with your stack:

- **🌐 Browsing**: Real-time research and documentation extraction.
- **💻 Infrastructure**: SSH & CLI interaction with Cisco, Juniper, Arista, and Linux.
- **📋 ITSM**: Full **ServiceNow** integration for Incidents, Changes, and CMDB.
- **📐 NetDesign**: Automated **Draw.io** diagram generation from natural language.
- **☁️ Cloud**: Native operators for AWS, Azure, and GCP.

---

## ⌨️ Essential Slash Commands

| Command | Description |
| :--- | :--- |
| `/session new` | Save current session and start a fresh one. |
| `/agents list` | Manage specialist A2A agents. |
| `/skills list` | View and add capabilities to the agent. |
| `/automata add` | Schedule a new background task. |
| `/middlewares` | Configure PII masking and context pruning. |
| `/memory` | View the agent's current persistent knowledge. |

---

## 📖 Usage Examples

### 🎮 Powered-Up Interactive CLI
Run the agent with intelligent context detection and a specific model configuration:
```bash
workerxy cli --model gpt-5.1-medium --subagent-model gpt-5.1-no-thinking --automatic-context-detection --association-window 5
```

### 🤖 Custom Headless Worker
Standard headless execution without the association overhead:
```bash
workerxy headless --model gpt-5.1-medium --subagent-model gpt-5.1-no-thinking
```

### 🔇 Less Noisy Logging
For a cleaner terminal experience, use the `warning` log level:
```bash
workerxy cli --log-level warning
```

---

## ⚙️ Quick Start

### 📋 Prerequisites
- Python 3.12+
- `uv` (recommended) or `pip`
- RabbitMQ (required for Discord/Headless modes)

### 🐳 Docker Installation (Recommended)
The easiest way to get started with all system dependencies (like RabbitMQ and browsers):

```bash
# Clone and enter
git clone https://github.com/nkxy007/workerxy.git
cd workerxy

# Option 1: Start the basic environment (RabbitMQ and MCP Server)
docker compose up -d rabbitmq mcp

# Option 2: Start the entire background suite (MCP, Headless worker)
docker compose up -d

# Run the agent CLI interactively (creates an ephemeral container overriding the mcp command)
docker compose run --rm mcp cli --model gpt-5.1-medium --subagent-model gpt-5.1-no-thinking --automatic-context-detection --association-window 5
```

### 🛠 Manual Installation
```bash
# Clone and enter
git clone https://github.com/nkxy007/workerxy.git
cd workerxy

# Install dependencies
pip install -e .

# Run the initialization script
python initializer.py
```

## 🚀 Activation Matrix

After installation and initialization, start your components using the `workerxy` multi-tool CLI.

| Command | Component | Description |
| :--- | :--- | :--- |
| `workerxy cli` | **Agent Cockpit** | Full-featured TUI for interactive troubleshooting. |
| `workerxy ui` | **Dashboard** | Web-based interface for visual monitoring (Streamlit). |
| `workerxy discord` | **Discord Bridge** | Connect your Discord server to the agent via RabbitMQ. |
| `workerxy headless` | **Background Worker** | Headless mode for processing jobs from a message queue. |
| `workerxy mcp` | **MCP Servers** | Launch the underlying Model Context Protocol servers. |
| `workerxy skill` | **Skill Manager** | CLI tool for creating and managing agent capabilities. |

---

Built with ❤️ by the XTOFTech Advanced Agentic Coding team.

