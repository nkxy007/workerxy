
import asyncio
import logging
from typing import List
from langchain_core.tools import tool
from a2a_capability.server import create_a2a_app
import uvicorn

# Configure logging for visibility
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("dns_deepagent")

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
    
    # We can pass these tools to the deep agent creation if we wanted a more complex agent
    # For now, we rely on the generic 'text' conversation where the LLM simulates being a DNS expert
    # OR we could inject a custom agent instance into create_a2a_app. 
    # To keep it simple but powerful, let's just define capabilities.
    
    app = create_a2a_app(
        agent_name="dns_deepagent",
        agent_description="Expert agent for Domain Name System (DNS) resolution, troubleshooting, and record management.",
        agent_capabilities=["resolve_domain", "check_records", "troubleshoot_dns"],
        port=port
    )
    
    uvicorn.run(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
