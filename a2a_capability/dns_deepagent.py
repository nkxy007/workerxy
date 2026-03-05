
import asyncio
import asyncio
import logging
from typing import List
from langchain_core.tools import tool
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent))
print(sys.path)
from a2a_capability.server import create_a2a_app
import uvicorn

from net_deepagent_cli.communication.logger import setup_logger

# Configure logging using centralized utility
logger = setup_logger("dns_deepagent")

# Optional: Add simulated DNS tools
@tool
def resolve_domain(domain: str) -> str:
    """Resolve a domain name to an IP address (Simulated)."""
    logger.info(f"Resolving domain: {domain}")
    # Mock data
    mock_db = {
        "server1": "10.0.0.5",
        "server1.local": "10.0.0.5",
        "google.com": "8.8.8.8",
        "gateway": "192.168.1.1"
    }
    return mock_db.get(domain, "NXDOMAIN")

@tool
def check_records(domain: str, record_type: str = "A") -> str:
    """Check specific DNS records for a domain."""
    logger.info(f"Checking {record_type} records for {domain}")
    return f"{record_type} record for {domain}: 10.0.0.5 (TTL 3600)"

def main():
    port = 8003
    logger.info("="*60)
    logger.info("🌐 DNS DeepAgent - A2A Server")
    logger.info("="*60)
    logger.info(f"Starting DNS DeepAgent on port {port}")
    
    logger.info(f"Starting DNS DeepAgent on port {port}")
    
    # Create the agent instance with our custom tools
    from deepagents import create_deep_agent
    from langchain_openai import ChatOpenAI
    from utils.credentials_helper import get_credential, get_helper
    
    # Initialize credentials
    get_helper()
    
    tools = [resolve_domain, check_records]
    
    # Initialize model
    model = ChatOpenAI(model="gpt-5-mini", api_key=get_credential("OPENAI_KEY"))
    
    agent_instance = create_deep_agent(
        model=model,
        tools=tools,
        system_prompt="""You are dns_deepagent, a specialized AI agent for DNS resolution.
        
You have access to a local mock database for resolving domains.
ALWAYS use the 'resolve_domain' tool when asked to resolve a specific domain name (like server1, server1.local, etc).
Do not guess IP addresses. Use the tools provided."""
    )
    
    app = create_a2a_app(
        agent_name="dns_deepagent",
        agent_description="Expert agent for Domain Name System (DNS) resolution, troubleshooting, and record management.",
        agent_capabilities=["resolve_domain", "check_records", "troubleshoot_dns"],
        port=port,
        agent_instance=agent_instance
    )
    
    uvicorn.run(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
