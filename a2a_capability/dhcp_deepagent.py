
import asyncio
import logging
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
logger = logging.getLogger("dhcp_deepagent")

def main():
    port = 8004
    logger.info("="*60)
    logger.info("🌐 DHCP DeepAgent - A2A Server")
    logger.info("="*60)
    logger.info(f"Starting DHCP DeepAgent on port {port}")
    
    app = create_a2a_app(
        agent_name="dhcp_deepagent",
        agent_description="Expert agent for Dynamic Host Configuration Protocol (DHCP) lease management and troubleshooting.",
        agent_capabilities=["check_lease", "get_ip_info", "release_renew"],
        port=port
    )
    
    uvicorn.run(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
