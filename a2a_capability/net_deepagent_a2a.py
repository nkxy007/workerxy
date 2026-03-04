
import asyncio
import logging
import os
import sys

# Add workspace root to path to ensure imports work correctly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langchain_openai import ChatOpenAI
from langgraph.store.memory import InMemoryStore

# Import existing creating logic or similar components
# We will reuse the structure of 'create_network_agent' but inject our middleware
from utils.credentials_helper import get_credential, get_helper
import os

# Initialize credentials
get_helper()

# Configure logging for visibility
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("net_deepagent_a2a")

async def main():
    logger.info("=== Starting Net DeepAgent with A2A Capability ===")
    
    # 1. Initialize A2A Middleware
    a2a_middleware = A2AHTTPMiddleware()
    
    # 2. Load Agents from Registry
    registry_path = os.path.join(os.path.dirname(__file__), "agents_registry.json")
    await a2a_middleware.register_agents_from_file(registry_path)
    
    # 3. Create the Network Agent (enhanced)
    # Note: The original create_network_agent function in net_deepagent.py 
    # doesn't explicitly accept a 'middleware' argument in its signature 
    # (based on the view_file of net_deepagent.py). 
    # So we might need to manually construct it or assume we can pass it via 'custom_system_prompt' hacking?
    #
    # Looking at net_deepagent.py: 
    # It calls `create_deep_agent(...)`. We need to intercept this or modify `net_deepagent.py` to accept middleware.
    # However, `create_deep_agent` from `deepagents` usually accepts `middleware`.
    #
    # Strategy: We will create the agent normally, then manually inject the A2A tools 
    # into the agent's tool set. This is a common pattern when we can't easily change the factory.
    # 
    # ACTUALLY, checking net_deepagent.py again... 
    # It seems `create_network_agent` returns a compiled graph (net_deep_agent).
    # It is harder to inject middleware AFTER creation if it is a compiled graph.
    #
    # BETTER STRATEGY: 
    # We will instantiate the A2A tools and pass them as "extra tools" if possible?
    # net_deepagent.py's `create_network_agent` takes `mcp_server_url`, models, etc.
    # It does NOT take an extra list of tools.
    #
    # We should probably modify `net_deepagent.py` to allow passing extra tools OR middleware.
    # BUT, to avoid modifying the original file too much (as per instructions "adapt it... create another folder"), 
    # I will replicate the necessary parts of `create_network_agent` here but WITH the A2A middleware.
    
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from prompts import network_activity_planner_agent_template
    from deepagents import create_deep_agent
    
    # ... (Reusing logic from net_deepagent.py) ...
    
    mcp_server_url = "http://localhost:8000/mcp"
    
    # MCP Client
    try:
        client = MultiServerMCPClient(
            {
                "network": {
                    "url": mcp_server_url,
                    "transport": "streamable_http",
                }
            }
        )
        mcp_tools = await client.get_tools()
    except Exception as e:
        logger.warning(f"Could not connect to MCP server, continuing without MCP tools: {e}")
        mcp_tools = []

    # Get A2A Tools
    a2a_tools = a2a_middleware.tools 
    logger.info(f"Loaded {len(a2a_tools)} A2A tools: {[t.name for t in a2a_tools]}")

    all_tools = mcp_tools + a2a_tools
    
    # Models
    main_model = ChatOpenAI(model="gpt-5.1-mini", api_key=get_credential("OPENAI_KEY")) 
    
    # Create Deep Agent with A2A Middleware
    # We pass the middleware to create_deep_agent if it supports it, 
    # OR we just pass the tools. Passing tools is often sufficient for the LLM to use them.
    # Middleware is useful for lifecycle hooks (before/after run).
    
    net_deep_agent = create_deep_agent(
        tools=all_tools,
        system_prompt=network_activity_planner_agent_template + "\n\nYou also have access to remote agents via A2A tools. Use them when you need specialized help (DNS, DHCP, etc).",
        model=main_model,
        store=InMemoryStore(),
        # middleware=[a2a_middleware] # If supported by deepagents.create_deep_agent
    )
    
    logger.info("Agent created successfully.")
    
    # Interactive Loop
    print("\n" + "="*50)
    print("🌐 Net DeepAgent (A2A Enabled) - Interactive Mode")
    print("="*50)
    print("Type 'exit' to quit.\n")
    
    while True:
        try:
            user_input = input("User: ")
            if user_input.lower() in ["exit", "quit"]:
                break
            
            print("\nAgent is thinking...")
            async for chunk in net_deep_agent.astream({"messages": [{"role": "user", "content": user_input}]}):
                # Simple streaming output
                if "messages" in chunk:
                     # For simplicity in this demo, just print the final message if it's there
                     pass
            
            # Since astream yields chunks, we might want to get the final response more cleanly
            # For this simple CLI, let's just invoke it to get the final result easily
            # (Note: doing invoke after astream in a loop is redundant but fine for demo clarity)
            # Actually, let's just use invoke for clarity in the demo loop
            
            # result = await net_deep_agent.ainvoke({"messages": [{"role": "user", "content": user_input}]})
            # print(f"Agent: {result['messages'][-1].content}\n")
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Error during execution: {e}")

    await a2a_middleware.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
