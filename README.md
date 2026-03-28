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
*   **Agent-Driven Scheduling**: The `automata_agent` subagent can programmatically schedule recurring tasks like "verify server status every 15 mins".
*   **Autonomous Execution**: WorkerXY handles the execution and logging even while you're offline.
*   **Full Lifecycle & Verification**: List, pause, resume, and inspect detailed execution logs via `/automata` or directly through the agent.

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
| `/automata` | List, add, or stop background tasks. |
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

# (Linux only) Ensure your user has Docker permissions
sudo usermod -aG docker $USER && newgrp docker

# Build the unified image
docker compose build

# Option 1: Start everything (MCPs, Headless, Discord, UI) in one container
docker compose up all

# Option 2: Run the smart CLI (Interactive Terminal with dual MCPs running in background)
docker compose run --rm cli

# Option 3: Start the smart Headless Worker (Headless loop + dual MCPs + Discord Bot)
docker compose up headless

# Option 4: Start the smart GUI (Streamlit Web UI + dual MCPs)
docker compose up gui
```

### 🌍 Run From Anywhere (Global Alias)
To avoid having to `cd` into the `workerxy` directory every time, simply create a global alias in your shell configuration (e.g., `~/.bashrc` or `~/.zshrc`):

```bash
# Add this line to your ~/.bashrc or ~/.zshrc
alias workerxy-docker='docker compose -f /path/to/your/cloned/workerxy/docker-compose.yml --project-directory /path/to/your/cloned/workerxy'

# Reload your shell
source ~/.bashrc

# Now you can start the UI from anywhere:
workerxy-docker up gui
```

### 🛠 Manual Installation
```bash
# Clone and enter
git clone https://github.com/nkxy007/workerxy.git
cd workerxy

# Install dependencies
pip install -e .

# (Optional) Install EVE-NG Lab tools
# Note: eve-ng requires a legacy version of 'rich'. 
# To avoid conflicts with modern tools, install it without dependencies:
pip install --no-deps eve-ng==0.2.7

# Run the initialization script
python initializer.py
```

## 🚀 Activation Matrix

After installation and initialization, start your components using the `workerxy` multi-tool CLI.

| Command | Component | Description |
| :--- | :--- | :--- |
| `workerxy start-cli` | **Smart CLI** | Multi-tool: Starts MCPs + launches Interactive TUI. |
| `workerxy start-headless` | **Smart Worker** | Multi-tool: Starts MCPs & Discord + launches Headless worker. |
| `workerxy start-gui` | **Smart Dashboard** | Multi-tool: Starts MCPs + launches Streamlit UI. |
| `workerxy start-all` | **Full Stack** | Multi-tool: Starts MCPs, Discord, Headless, and UI in one go. |
| `workerxy mcp base` | **Core MCP** | Launch the primary network/ITSM tool server (Port 8000). |
| `workerxy mcp lab` | **Lab MCP** | Launch the EVE-NG/Lab automation server (Port 8001). |
| `workerxy cli` | **Direct CLI** | Launch the TUI directly (requires background MCPs). |
| `workerxy ui` | **Direct UI** | Launch Streamlit directly (requires background MCPs). |
| `workerxy skill` | **Skill Manager** | CLI tool for creating and managing agent capabilities. |

Extra examples:
 `workerxy cli --model gpt-5.1-medium --subagent-model gpt-5.1-no-thinking --automatic-context-detection --association-window 5`

 `workerxy headless --model gpt-5.1-medium --subagent-model gpt-5.1-no-thinking`

 `docker compose run --rm cli --model gpt-5.1-medium --subagent-model gpt-5.1-no-thinking --automatic-context-detection --association-window 5 --log-level WARNING`

---

Built with ❤️ by the XTOFTech Advanced Agentic Coding team.

