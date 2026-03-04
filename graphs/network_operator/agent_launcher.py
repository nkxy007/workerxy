import sys
import asyncio
import os
from pathlib import Path

# Add the project root and graphs directory to sys.path
root_dir = Path(__file__).resolve().parent.parent.parent
graphs_dir = root_dir / "graphs"
for d in [root_dir, graphs_dir]:
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))

from graphs.network_operator.agent import build_graph, run_investigation
from langchain_mcp_adapters.client import MultiServerMCPClient
from utils.credentials_helper import get_credential, get_helper

# Initialize credentials
get_helper()

# Credentials are automatically handled by CredentialsHelper

async def main():
    # 1. Connect to MCP Server to get tools
    # Ensure mcp_servers.py is running
    mcp_url = "http://localhost:8000/mcp"
    print(f"Connecting to MCP server at {mcp_url}...")
    
    try:
        client = MultiServerMCPClient(
            {
                "network": {
                    "url": mcp_url,
                    "transport": "streamable_http",
                }
            }
        )
        tools = await client.get_tools()
        print(f"Successfully retrieved {len(tools)} tools from MCP.")
    except Exception as e:
        print(f"Failed to connect to MCP server: {e}")
        print("Ensure 'python mcp_servers.py' is running in another terminal.")
        return

    # 2. Build the Network Operator graph
    print("Building Network Operator graph...")
    # build_graph handles its own model initialization via config defaults
    graph = build_graph(
        tools=tools,
        interrupt_before_destructive=False
    )

    # 3. Run a sample investigation
    problem = "There is a report of OSPF connection issue on router with management IP 192.168.81.226. Investigate the root cause. ssh to the device."
    print(f"\nStarting investigation: {problem}\n")
    
    try:
        result = await run_investigation(
            graph, 
            problem, 
            thread_id="investigation_1"
        )
        
        print("\n=== Investigation Result ===")
        # The result of run_investigation is the final state
        if "rca" in result:
             print(f"RCA: {result['rca']}")
        else:
             print(f"Final Message: {result['messages'][-1].content}")
    except Exception as e:
        print(f"Investigation failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
