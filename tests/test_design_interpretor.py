import asyncio
import os
import sys
from langchain_core.messages import HumanMessage

# Add workspace root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from graphs.design_interpretor import design_interpretor_graph

async def test_design_interpretor():
    print("Starting Design Interpreter Test...")
    
    # Path to a sample diagram in the workspace
    sample_image = "/home/toffe/workspace/agentic/small_network_diagram.png"
    
    if not os.path.exists(sample_image):
        print(f"Sample image not found: {sample_image}")
        return

    # Check for API key
    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not set in environment.")
        # Try to load from creds if available (mocking the environment setup)
        try:
            import creds
            os.environ["OPENAI_API_KEY"] = creds.OPENAI_KEY
            print("Loaded API key from creds.py")
        except ImportError:
            print("Could not import creds.py")
            return

    initial_state = {
        "messages": [HumanMessage(content=f"Analyze this network diagram: {sample_image}")],
        "model_name": "openai",
        "api_key": os.environ.get("OPENAI_API_KEY")
    }

    print(f"Running graph with image: {sample_image}")
    try:
        # Using invoke for a cleaner output in the test
        final_state = await design_interpretor_graph.ainvoke(initial_state)
        
        print("\n--- Test Results ---")
        if final_state.get("error"):
            print(f"Error: {final_state['error']}")
        
        if final_state.get("result"):
            result = final_state["result"]
            print(f"Summary: {result.summary}")
            print(f"Devices found: {len(result.devices)}")
            for dev in result.devices:
                print(f"  - {dev.name} ({dev.brand})")
            print(f"Links found: {len(result.links)}")
            print(f"Protocols found: {len(result.protocols)}")
        else:
            print("No structured result found.")
            print("Last message content:")
            print(final_state["messages"][-1].content)
            
    except Exception as e:
        print(f"An error occurred during verification: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_design_interpretor())
