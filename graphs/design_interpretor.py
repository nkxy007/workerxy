from typing import Annotated, List, Optional, TypedDict
import operator
from pydantic import BaseModel, Field
from langgraph.graph import START, END, StateGraph
from langchain_core.messages import AnyMessage, HumanMessage, AIMessage, SystemMessage
from ai_helper import AIHelper
import json
import os
import sys

# Add workspace root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Data Models
class Device(BaseModel):
    name: str = Field(description="The hostname or name of the device")
    management_ip: Optional[str] = Field(description="Management IP address of the device", default=None)
    brand: str = Field(description="Brand of the device (Cisco, Juniper, etc.)")
    role: Optional[str] = Field(description="Role of the device (Router, Switch, PC, etc.)", default=None)

class Link(BaseModel):
    from_device: str = Field(description="Name of the source device")
    from_interface: str = Field(description="Interface name on the source device")
    to_device: str = Field(description="Name of the destination device")
    to_interface: str = Field(description="Interface name on the destination device")
    link_ip: Optional[str] = Field(description="IP address or subnet of the link", default=None)

class Protocol(BaseModel):
    name: str = Field(description="Name of the protocol (OSPF, BGP, etc.)")
    devices: List[str] = Field(description="List of devices participating in the protocol")
    details: str = Field(description="Details such as Area ID, AS Number, etc.")

class FullDesign(BaseModel):
    devices: List[Device] = Field(description="List of all devices in the topology")
    links: List[Link] = Field(description="List of all links between devices")
    protocols: List[Protocol] = Field(description="List of all protocols configured")
    summary: str = Field(description="A high-level summary of the network design")

# State definition
class InterpretorState(TypedDict):
    messages: Annotated[List[AnyMessage], operator.add]
    image_path: str
    model_name: str
    api_key: str
    result: Optional[FullDesign]
    error: Optional[str]

# Prompt from image_tool.py
VISION_PROMPT = """
Analyze the provided network diagram and extract all relevant details. 
Return your findings in the following JSON format:

{
  "devices": [
    {
      "name": "device hostname",
      "management_ip": "IP if present",
      "brand": "Cisco/Juniper/etc",
      "role": "Router/Switch/etc"
    }
  ],
  "links": [
    {
      "from_device": "device name",
      "from_interface": "interface name",
      "to_device": "device name",
      "to_interface": "interface name",
      "link_ip": "IP address if present"
    }
  ],
  "protocols": [
    {
      "name": "OSPF/BGP/etc",
      "devices": ["list of devices"],
      "details": "Area X, ASN Y, etc"
    }
  ],
  "summary": "High-level overview of the topology"
}

IMPORTANT: Ensure all keys are present. If links or protocols are not found, return empty lists. Use 'name' for the device name/hostname.
"""

from langchain_core.runnables import RunnableConfig

# Nodes
def extract_context(state: InterpretorState):
    """Extract image path from the last message if not already set."""
    if state.get("image_path"):
        return {}
    
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "content"):
        content = last_msg.content
        # Simple heuristic to find a file path ending in .png, .jpg, .jpeg
        import re
        match = re.search(r"(/[^\s]+\.(?:png|jpg|jpeg))", content, re.IGNORECASE)
        if match:
            return {"image_path": match.group(1)}
    
    return {"error": "Could not find image path in message"}

def interpret_image(state: InterpretorState, config: RunnableConfig):
    """Analyze the image using AIHelper and return the findings."""
    if state.get("error"):
        return {}
        
    image_path = state.get("image_path")
    
    # Get config from configurable
    configurable = config.get("configurable", {})
    model_name = configurable.get("model_name", "openai")
    api_key = configurable.get("api_key")
    
    if not image_path or not os.path.exists(image_path):
        return {"error": f"Image path {image_path} does not exist", "messages": [AIMessage(content=f"Error: Image path {image_path} not found.")]}
    
    ai_helper = AIHelper(api_key, model=model_name)
    try:
        print(f"Interpreting image {image_path} with model {model_name}...")
        encoded_image = ai_helper.encode_image(image_path)
        image_type = "png"
        if image_path.lower().endswith((".jpg", ".jpeg")):
            image_type = "jpeg"
        
        analysis_result = ai_helper.get_image_analysis(encoded_image, VISION_PROMPT, temperature=0.5, image_type=image_type)
        return {"messages": [AIMessage(content=analysis_result)]}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e), "messages": [AIMessage(content=f"Error during analysis: {str(e)}")]}

def parse_structured_data(state: InterpretorState):
    """Parse the LLM output into the FullDesign model."""
    if state.get("error"):
        return {}
        
    last_message = state["messages"][-1]
    content = last_message.content
    
    # Try to find JSON in the content
    try:
        content_str = str(content)
        # Basic cleanup if Markdown code blocks are present
        if "```json" in content_str:
            json_str = content_str.split("```json")[1].split("```")[0].strip()
        elif "```" in content_str:
            json_str = content_str.split("```")[1].split("```")[0].strip()
        else:
            # Try to find any { ... } block
            import re
            match = re.search(r'(\{.*\})', content_str, re.DOTALL)
            if match:
                json_str = match.group(1)
            else:
                json_str = content_str
        
        data = json.loads(json_str)
        
        # Manual fix for common aliases
        if "devices" in data:
            for dev in data["devices"]:
                if "hostname" in dev and "name" not in dev:
                    dev["name"] = dev["hostname"]
        
        # Ensure lists exist
        for key in ["devices", "links", "protocols"]:
            if key not in data:
                data[key] = []
        if "summary" not in data:
            data["summary"] = "No summary provided."
            
        result = FullDesign(**data)
        
        summary_msg = f"Design Interpretation Complete.\nSummary: {result.summary}\nDevices: {len(result.devices)}, Links: {len(result.links)}, Protocols: {len(result.protocols)}"
        return {"result": result, "messages": [AIMessage(content=summary_msg)]}
    except Exception as e:
        print(f"Structured parsing failed: {e}")
        # Return a message indicating parsing failure but keeping the raw analysis available
        return {"messages": [AIMessage(content=f"Note: Could not parse output into fully structured data ({str(e)}), but raw analysis is available in previous message.")]}

# Build the Graph
workflow = StateGraph(InterpretorState)
workflow.add_node("extract_context", extract_context)
workflow.add_node("interpret_image", interpret_image)
workflow.add_node("parse_structured_data", parse_structured_data)

workflow.add_edge(START, "extract_context")
workflow.add_edge("extract_context", "interpret_image")
workflow.add_edge("interpret_image", "parse_structured_data")
workflow.add_edge("parse_structured_data", END)

design_interpretor_graph = workflow.compile()

# Subagent Integration helper
def get_design_interpretor_subagent(model_name: str = "openai", api_key: str = None):
    """Return a CompiledSubAgent configuration."""
    if api_key is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        
    return {
        "name": "design_interpretor",
        "description": "Specialized agent that reads network diagram images (png, jpg, jpeg) and converts them into structured network design data. Provide the absolute path to the diagram image in your prompt. Result includes devices, links, protocols and a summary.",
        "runnable": design_interpretor_graph.with_config({
            "configurable": {
                "model_name": model_name,
                "api_key": api_key
            }
        })
    }

if __name__ == "__main__":
    # Simple CLI test
    import asyncio
    
    async def run_test():
        path = "small_network_diagram.png"
        if os.path.exists(path):
            initial_state = {
                "messages": [HumanMessage(content=f"Analyze this image: {path}")],
                "image_path": path,
                "model_name": "openai",
                "api_key": os.environ.get("OPENAI_API_KEY")
            }
            async for chunk in design_interpretor_graph.astream(initial_state):
                print(chunk)
    
    # asyncio.run(run_test())
