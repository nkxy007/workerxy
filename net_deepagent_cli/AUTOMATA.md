# Automata: Scheduled Agent Tasks

The Automata feature allows the Net DeepAgent to run tasks in the background on a schedule. This is useful for periodic monitoring, health checks, and automated reporting.

## Overview

- **Persistent**: Tasks are saved to `~/.net-deepagent/<agent-name>/automata.json` and persist across restarts.
- **Background Execution**: Tasks run asynchronously in the background loop of the agent.
- **Result Logging**: Execution results are saved to `~/.net-deepagent/<agent-name>/automata_results/`.

## Usage

Access the Automata menu by typing:

```bash
/automata
```

Or trigger a command directly:

```bash
/automata every 5 minutes check network latency
```

## Commands

| Command | Description | Example |
|str|str|str|
|---|---|---|
| `list` | List all scheduled tasks. | `list` |
| `add` | Add a new scheduled task. | `add Check VPN every 10min` |
| `remove` | Remove a task by ID. | `remove a1b2c3d4` |
| `resume` | Resume a stale task. | `resume a1b2c3d4` |
| `logs` | List execution logs for a task. | `logs a1b2c3d4` |
| `view` | View the content of a log file. | `view a1b2c3d4_20230101_120000.md` |
| `help` | Show available commands. | `help` |
| `back` | Return to the main chat. | `back` |

## Scheduling Syntax

Automata supports flexible natural language scheduling:

- **Explicit**: `add <prompt> every <N> <unit>`
  - `add check status every 30 seconds`
- **Implicit**: `<prompt> every <N> <unit>`
  - `check status every 30s`
- **Natural Language**:
  - `run a health check daily` (Uses LLM to interpret "daily" as 86400 seconds)
  - `every 5 minutes scan for critical incidents`

Supported units: `seconds` (s), `minutes` (m), `hours` (h).

## Architecture

- **Manager**: `AutomataManager` in `automata.py` handles the `AsyncIOScheduler`.
- **Storage**: Tasks are stored as JSON; Logs are stored as Markdown.
- **Integration**: Hooked into `loop.py` main interactive loop.
