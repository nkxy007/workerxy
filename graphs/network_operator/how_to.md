# How to Use and Integrate with Network Operator

The `network_operator` is a principal-engineer-level diagnostic agent designed to troubleshoot complex multi-vendor network environments. It uses a LangGraph-based architecture with tiered nodes for planning, execution, and synthesis.

## Core Components
- **Planner**: Decision-making core that forms hypotheses and designs diagnostic plans.
- **Executor**: Technician node that maps plan steps to native MCP tools.
- **Compressor**: Summarizes raw tool output into digestible findings.
- **Synthesizer**: Produces the final structured Root Cause Analysis (RCA).

---

## Integration Guide

### 1. Prerequisite: MCP Server
The agent relies on the `mcp_servers.py` for tool execution. Ensure your MCP server is running and exposes the following tools correctly:
- `net_run_commands_on_device`: For remote device SSH access.
- `execute_shell_command`: For local diagnostic tools (ping, mtr, curl).
- `execute_generated_code`: For complex log analysis or processing.

### 2. Manual Execution
You can use `agent_launcher.py` (if provided) or instantiate the graph directly in your application:

```python
from network_operator.agent import build_graph, run_investigation
from mcp_servers import get_tools # Assuming a tool loader exists

# 1. Initialize tools from MCP
tools = get_tools()

# 2. Build the graph
graph = build_graph(tools=tools)

# 3. Trigger an investigation
result = await run_investigation(
    graph, 
    problem_statement="BGP session flapping on core-router-1",
    thread_id="unique-session-id"
)

print(result["rca"])
```

---

## Testing Guide

All tests should be run within the `test_langchain_env` conda environment.

### 1. Set Up Environment
```bash
conda activate test_langchain_env
```

### 2. Run Automated Tests
The test suite covers unit tests for every node, state transitions, and end-to-end graph flows.

```bash
# Run all tests
pytest graphs/network_operator/tests/

# Run specific test file
pytest graphs/network_operator/tests/test_nodes.py
```

### 3. Verification Details
- **Unit Tests (`test_nodes.py`)**: Verify individual node logic using mocked models.
- **Graph Tests (`test_graph.py`)**: Verify the full orchestration loop including state persistence.
- **State Tests (`test_state.py`)**: Verify schema validation and Pydantic model integrity.

---

## Key Design Principles
- **Falsifiable Hypotheses**: The planner must form hypotheses that can be proven "rejected" or "confirmed".
- **Structured RCA**: Every session ends with a structured `RCAOutput` containing remediation steps and confidence scores.
- **No Placeholders**: The agent is designed to use real diagnostic tools rather than simulations where possible.
