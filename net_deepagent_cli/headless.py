import asyncio
import sys
import argparse
import logging
import aio_pika
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

import creds
from net_deepagent_cli.agent import create_cli_agent
from net_deepagent_cli.communication.listener import run_agent_listener
from net_deepagent_cli.ui import TerminalUI
from warnings import filterwarnings
filterwarnings("ignore", category=DeprecationWarning)
filterwarnings("ignore", category=RuntimeWarning)
# ignore typing.NotRequired
filterwarnings("ignore", category=FutureWarning)
filterwarnings("ignore", category=UserWarning)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("net_deepagent_headless")

async def run_headless():
    parser = argparse.ArgumentParser(description="Net DeepAgent Headless - Process jobs from RabbitMQ")
    
    parser.add_argument("--agent", default="net-agent", help="Agent name")
    parser.add_argument("--model", default="gpt-5-mini", help="Main model to use")
    parser.add_argument("--subagent-model", default="gpt-5-mini-minimal", help="Subagent model to use")
    parser.add_argument("--design-model", default="gpt-5.1", help="Design model to use")
    parser.add_argument("--mcp-server", default="http://localhost:8000/mcp", help="MCP server URL")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], help="Set the logging level")
    
    args = parser.parse_args()

    # Set log level immediately
    from net_deepagent_cli.communication.logger import set_log_level
    set_log_level(args.log_level)
    
    # We still create a TerminalUI instance but it will be largely suppressed
    # or used for formatted logging if needed.
    from net_deepagent_cli.communication.logger import comm_logger
    ui = TerminalUI(args.agent, logger=comm_logger)
    
    logger.info(f"Initializing headless agent '{args.agent}'... with args: {args}")
    
    # RabbitMQ URL from creds
    rabbitmq_url = f"amqp://{creds.RABBITMQUSER}:{creds.RABBITMQ_PASSWORD}@localhost:5672/"
    
    try:
        # Step 1: Create the agent
        # We pass None for UI to agent creation if we want truly headless, 
        # but create_cli_agent expects some UI for security callbacks if auto_approve is False.
        # For now, we'll pass our UI and assume jobs are auto-approved in headless mode 
        # unless user specifies otherwise.
        from net_deepagent_cli.communication.tools import send_chat_message
        
        agent = await create_cli_agent(
            agent_name=args.agent,
            mcp_server_url=args.mcp_server,
            main_model_name=args.model,
            subagent_model_name=args.subagent_model,
            design_model_name=args.design_model,
            auto_approve=True, # Headless mode usually implies auto-approve or remote approval
            ui=ui,
            extra_tools=[send_chat_message]
        )
        
        # Step 2: Connect to RabbitMQ
        logger.info(f"Connecting to RabbitMQ at {rabbitmq_url}...")
        connection = await aio_pika.connect_robust(rabbitmq_url)
        
        # Step 3: Start listener
        async with connection:
            logger.info("Agent starting listener loop...")
            await run_agent_listener(agent, connection, ui=ui)
            
    except Exception as e:
        logger.error(f"Failed to run headless agent: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(run_headless())
    except KeyboardInterrupt:
        logger.info("Headless agent stopped by user.")
