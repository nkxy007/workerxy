# 🤖 WorkerXY

**The Ultimate AI Copilot for Network Operations & Automation.**

WorkerXY is a powerful, agentic AI system designed to streamline network diagnostics, cloud management, and datacenter operations. Whether you're troubleshooting BGP drifts in a local lab or managing global scale AWS clusters, WorkerXY is your specialist companion.

---

## 🌟 Key Features

### 🤖 Intelligent Agent Core
- **Interactive TUI**: A rich, turn-based "Agent Cockpit" built with `rich`.
- **Streaming Responses**: Real-time token-by-token output.
- **Security First**: Mandatory user approval for sensitive shell and code execution (unless `--auto-approve` is set).

### 🔌 Specialist Agent Registry (`/agents`)
Dynamically load specialist agents like:
- `dns_deepagent`: Deep DNS resolution and diagnostics.
- `dhcp_deepagent`: DHCP lease management and troubleshooting.

### 🧠 Persistent Memory & Skills
- **Contextual Memory**: Automatically remembers past interactions to provide continuity.
- **Extensible Skills**: Extract new capabilities directly from documentation using `/skills add`.

### 💾 Session & Drift Management
- **Topic Drift Detection**: Suggests new sessions when the conversation shifts dramatically.
- **Interaction Association**: "Remember that BGP issue?" — WorkerXY can find and resume relevant past sessions.

### ⚙️ Automata (Scheduled Background Tasks)
- **Autonomous Operations**: Schedule recurring tasks (e.g., "verify server status every 15 mins") that run in the background.
- **Set-and-Forget**: WorkerXY handles the execution and logging while you focus on other work.
- **Robust Management**: List, pause, resume, and inspect detailed execution logs via `/automata`.

### 🛡️ Smart Middlewares
- **PII Masking**: Automatically pseudonymize IPs, MACs, and sensitive URLs.
- **Context Pruning**: Intelligent summarization as you approach model token limits.

---

## 🎨 User Interfaces

### 🏎️ Agent Cockpit (CLI)
A high-performance terminal UI designed for operational awareness.
- **Separated Views**: Command history, live tool execution, and background logs.
- **Command Palette**: Full tab-autocompletion for all Slash-commands (`/agents`, `/memory`, `/session`, etc.).

### 🌐 WorkerXY Dashboard (Streamlit)
A modern, web-based interface for visual interaction and monitoring.
- **Real-time Monitoring**: Track agent state and tool logs visually.
- **Configuration Management**: Hot-reload middlewares and agent settings via the web.

---

## 🚀 Quick Start

### 📋 Prerequisites
- Python 3.12+
- `uv` or `pip`
- RabbitMQ (for Headless/Discord mode)

### ⚙️ Installation

```bash
# Clone the repository
git clone https://github.com/nkxy007/workerxy.git
cd workerxy

# Install dependencies using uv (recommended)
uv sync

# Or using pip
pip install .
```

### 🏃 Running WorkerXY

#### 🎮 Interactive CLI (Cockpit)
```bash
workerxy cli
```

#### 🌐 Web UI
```bash
streamlit run ui/app.py
```

#### 🤖 Headless Mode (Worker)
Runs the agent as a background process listening for jobs via RabbitMQ.
```bash
workerxy headless
```

#### 💬 Discord Bridge
Connect your Discord server to WorkerXY.
```bash
workerxy discord
```

---

## 🔧 Deep Tool Integrations

WorkerXY leverages the **Model Context Protocol (MCP)** and custom skills to interact with your entire infrastructure:

- **🌐 Web Browsing**: Real-time research and documentation extraction using the integrated browser tool.
- **💻 SSH & CLI**: Direct, secure interaction with network devices (Cisco, Juniper, Arista) and Linux servers.
- **📡 API Connectivity**: Native support for RESTful APIs (e.g., Mist WiFi, Meraki, custom vendor endpoints).
- **📋 ITSM & Workflow**: Full integration with **ServiceNow** for incident tracking, change management, and CMDB updates.
- **☁️ Cloud Operators**: Comprehensive AWS, Azure, and GCP management.
- **📐 NetDesign**: Automated Draw.io diagram generation from natural language or network discovery.


---

## 📄 Documentation
- [CLI Features Guide](features_cli.md)
- [Debugging Guide](DEBUGGING_GUIDE.md)
- [Testing Guide](PHASE1_TESTING_GUIDE.md)

---

Built with ❤️ by the Advanced Agentic Coding team.
