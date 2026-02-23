
import asyncio
import logging
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from a2a_capability.server import create_a2a_app
import uvicorn
from langchain_core.tools import tool

# Configure logging for visibility
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("dhcp_deepagent")


DHCP_POOLS = [
    {
        "name": "vlan10",
        "subnet": "10.10.10.0/24",
        "range": "10.10.10.100-10.10.10.200",
        "gateway": "10.10.10.254",
        "dns": "[1.1.1.1]"
    },
    {
        "name": "vlan20",
        "subnet": "10.10.20.0/24",
        "range": "10.10.20.100-10.10.20.200",
        "gateway": "10.10.20.254",
        "dns": "[I8.8.8.8]"
    }
]

@tool
def check_dhcp_lease():
    """Check if a specific IP address is leased to a MAC address."""
    pass

@tool
def get_ip_info(ip_address):
    """Get information about a specific IP address based on the info provided when the host did a DHCP request.
    params:
        ip_address: the IP address to check
    returns:
        str: information about the IP address
    NOTE: Not Implemented yet
    """
    pass

@tool
def check_dhcp_pool(subnet: str) -> str:
    """check if a subnet DHCP pool exist
    params:
        subnet: the subnet to check
    returns:
        str: statement whether pool exist or not
    """
    for pool in DHCP_POOLS:
        if pool["subnet"] == subnet:
            return f"DHCP pool {pool['name']} exist with details {pool}"
    return f"DHCP pool {subnet} does not exist"

def main():
    from deepagents import create_deep_agent
    import creds
    from langchain_openai import ChatOpenAI
    port = 8004
    logger.info("="*60)
    logger.info("🌐 DHCP DeepAgent - A2A Server")
    logger.info("="*60)
    logger.info(f"Starting DHCP DeepAgent on port {port}")
    
    model = ChatOpenAI(model="gpt-5-mini", api_key=creds.OPENAI_KEY)
    tools = [check_dhcp_pool, get_ip_info, check_dhcp_lease]
    dhcp_agent_instance = create_deep_agent(
        model=model,
        tools=tools,
        system_prompt="""You are dhcp service deepagent, a specialized AI agent for DNS resolution.
        You have access to a local dhcp server configuration for dhcp leases, as well as tools to verify dhcp service status.
        Do not guess IP addresses. Use the tools provided."""
    )
    app = create_a2a_app(
        agent_name="dhcp_deepagent",
        agent_description="Expert agent for Dynamic Host Configuration Protocol (DHCP) lease management and troubleshooting.",
        agent_capabilities=["check_dhcp_pool", "get_ip_info", "check_dhcp_lease"],
        port=port,
        agent_instance=dhcp_agent_instance
    )
    
    uvicorn.run(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
