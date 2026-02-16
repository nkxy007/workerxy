import asyncio
import os
import sys
from unittest.mock import AsyncMock, patch
from langchain_core.messages import HumanMessage

# Add workspace root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mocking MultiServerMCPClient to avoid dependency on a running server
mock_client = AsyncMock()
mock_client.get_tools.return_value = []

@patch("net_deepagent.MultiServerMCPClient", return_value=mock_client)
async def test_agent_integration(mock_mcp):
    from net_deepagent import create_network_agent
    
    print("Initializing Integrated Network Agent...")
    agent = await create_network_agent(
        main_model_name="gpt-5.1",
        subagent_model_name="gpt-5-mini-minimal",
        design_model_name="gpt-5.1"
    )
    
    sample_image = "/home/toffe/workspace/agentic/small_network_diagram.png"
    if not os.path.exists(sample_image):
        print(f"Sample image not found: {sample_image}")
        return

    print(f"Testing delegation to design_interpretor for image: {sample_image}")
    
    # We want to see if the agent picks the right subagent.
    # We'll use a prompt that strongly suggests using the design interpreter.
    prompt = f"I have a network diagram at {sample_image}. Can you analyze it and tell me what devices are in it?"
    
    try:
        async for chunk in agent.astream({"messages": [HumanMessage(content=prompt)]}):
            # Pretty print chunks to see the tool calls and subagent delegation
            if "model" in chunk and "messages" in chunk["model"]:
                msg = chunk["model"]["messages"][-1]
                msg.pretty_print()
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                   for tc in msg.tool_calls:
                       if tc["name"] == "task" and tc["args"].get("subagent_type") == "design_interpretor":
                           print("\n[SUCCESS] Main agent correctly identified and called the 'design_interpretor' subagent!")
            elif "tools" in chunk and "messages" in chunk["tools"]:
                chunk["tools"]["messages"][-1].pretty_print()
                
    except Exception as e:
        print(f"Integration test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Ensure API keys are present for the models
    import creds
    os.environ["OPENAI_API_KEY"] = creds.OPENAI_KEY
    os.environ["ANTHROPIC_API_KEY"] = creds.ANTHROPIC_KEY
    
    asyncio.run(test_agent_integration())
