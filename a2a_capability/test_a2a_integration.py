
import asyncio
import logging
import os
import sys

# Add workspace root to path to ensure imports work correctly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langchain_openai import ChatOpenAI
from langgraph.store.memory import InMemoryStore
from deepagents import create_deep_agent
from a2a_capability.middleware import A2AHTTPMiddleware
import creds

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_a2a")

async def test_a2a_integration():
    """Test A2A integration with DNS and DHCP agents"""

    logger.info("=== Testing A2A Integration ===")

    # 1. Initialize A2A Middleware
    a2a_middleware = A2AHTTPMiddleware()

    # 2. Load Agents from Registry
    registry_path = os.path.join(os.path.dirname(__file__), "agents_registry.json")
    await a2a_middleware.register_agents_from_file(registry_path)

    # 3. Get A2A Tools
    a2a_tools = a2a_middleware.tools
    logger.info(f"Loaded {len(a2a_tools)} A2A tools: {[t.name for t in a2a_tools]}")
    logger.info(f"loaded tools: {a2a_tools}")

    # 4. Create Simple Agent with A2A Tools
    main_model = ChatOpenAI(model="gpt-4o-mini", api_key=creds.OPENAI_KEY)

    agent = create_deep_agent(
        tools=a2a_tools,
        system_prompt="You are a network administrator assistant with access to specialized agents for DNS and DHCP tasks. Use the appropriate agent tools when needed.",
        model=main_model,
        store=InMemoryStore(),
    )

    logger.info("Agent created successfully with A2A tools")

    # 5. Test Query 1: DNS Query
    print("\n" + "="*70)
    print("Test 1: Asking about DNS resolution")
    print("="*70)
    query1 = "Can you help me find out about DNS records for server1?"
    print(f"Query: {query1}\n")

    result1 = await agent.ainvoke({"messages": [{"role": "user", "content": query1}]})
    response1 = result1['messages'][-1].content
    print(f"Response:\n{response1}\n")

    # 6. Test Query 2: List Available Tools
    print("\n" + "="*70)
    print("Test 2: Checking what specialized agents are available")
    print("="*70)
    query2 = "What specialized network agents do you have access to?"
    print(f"Query: {query2}\n")

    result2 = await agent.ainvoke({"messages": [{"role": "user", "content": query2}]})
    response2 = result2['messages'][-1].content
    print(f"Response:\n{response2}\n")

    # 7. Cleanup
    await a2a_middleware.cleanup()

    print("\n" + "="*70)
    print("✅ A2A Integration Test Completed Successfully!")
    print("="*70)

    return True

if __name__ == "__main__":
    try:
        asyncio.run(test_a2a_integration())
    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)
        sys.exit(1)
