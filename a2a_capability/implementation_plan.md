# A2A Capability Implementation Plan

## Objective
Enable `net_deepagent` to discover and communicate with other specialized agents (`dns_deepagent`, `dhcp_deepagent`,...) using the Agent-to-Agent (A2A) protocol.

## Directory Structure
We will create a new directory `a2a_capability` with the following components:

```
agentic/
  a2a_capability/
    __init__.py
    agents_registry.json # Registry file for dynamic agent discovery
    client.py            # A2AHTTPClient implementation
    middleware.py        # A2AHTTPMiddleware for DeepAgent integration
    server.py            # A2AServer and FastAPI wrapper implementation
    dns_deepagent.py     # DNS specialized agent server
    dhcp_deepagent.py    # DHCP specialized agent server
    net_deepagent_a2a.py # Enhanced net_deepagent with A2A client capabilities
```

## Step-by-Step Implementation

### 1. Core A2A Infrastructure (`client.py`, `middleware.py`, `server.py`)
Refactor the existing logic from `a2a_capability_demo` into reusable modules:
- **`client.py`**: Contains `A2AHTTPClient`. Handles HTTP requests, JSON-RPC formatting, and `agent.json` discovery.
- **`middleware.py`**: Contains `A2AHTTPMiddleware`. 
    - Registers remote agents and generates LangChain `tools` dynamically based on the remote agent's capabilities.
    - **New**: Adds a method `register_agents_from_file(file_path)` to load agent configurations (name, URL) from a JSON file.
- **`server.py`**: Contains `A2AServer` and `create_a2a_app`. Wraps any `DeepAgent` into a FastAPI A2A server.

### 2. Specialized Agents (`dns_deepagent.py`, `dhcp_deepagent.py`)
Implement two new agents that act as servers:
- **`dns_deepagent.py`**:
    - Listens on a specific port (e.g., 8003).
    - specialized tools/knowledge: Resolving domain names, checking DNS records (mocked for demo).
    - Capabilities: `["resolve_domain", "check_records"]`.
- **`dhcp_deepagent.py`**:
    - Listens on a specific port (e.g., 8004).
    - specialized tools/knowledge: Lease checks, IP allocation info (mocked or simple logic).
    - Capabilities: `["check_lease", "get_ip_info"]`.

### 3. Dynamic Discovery Registry (`agents_registry.json`)
Create a JSON file that acts as the "yellow pages" for agents.
```json
{
    "dns_deepagent": "http://localhost:8003",
    "dhcp_deepagent": "http://localhost:8004"
}
```
To add a new agent, the user simply updates this file.

### 4. Enhanced Net DeepAgent (`net_deepagent_a2a.py`)
Adapt the logic from `net_deepagent.py` to include A2A capabilities:
- Import `create_network_agent` logic.
- Initialize `A2AHTTPMiddleware`.
- **Dynamic Registration**: Load the `agents_registry.json` file and register all agents found therein.
- Add the middleware to the agent's configuration.
- The `net_deepagent` will automatically have tools to communicate with any agent listed in the registry.

## Usage Workflow (Example)
1. User starts `dns_deepagent.py` (server).
2. User starts `dhcp_deepagent.py` (server).
3. User verifies/updates `agents_registry.json`.
4. User runs `net_deepagent_a2a.py`.
5. User asks `net_deepagent`: "Check if the hostname 'server1' has a valid IP and if its DHCP lease is active."
6. `net_deepagent` plans and executes using the dynamically discovered agents.

## Next Steps
- Review this plan.
- Proceed with implementation of the files.
