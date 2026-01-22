
import asyncio
import json
import logging
import os
from typing import Dict, List, Any, Optional

from langchain_core.tools import tool, StructuredTool
from langchain.agents.middleware import AgentMiddleware

from a2a_capability.client import A2AHTTPClient

# Configure logging
logger = logging.getLogger(__name__)

class A2AHTTPMiddleware(AgentMiddleware):
    """Middleware that adds real HTTP-based A2A communication to DeepAgent"""
    
    def __init__(self):
        super().__init__()
        self.remote_agents: Dict[str, A2AHTTPClient] = {}
        self._tools_cache = None
    
    async def register_remote_agent(self, name: str, base_url: str):
        """Register and discover a remote A2A agent via HTTP"""
        logger.info(f"Registering remote agent '{name}' at {base_url}")
        try:
            client = A2AHTTPClient(base_url)
            await client.discover_agent()
            self.remote_agents[name] = client
            
            # Clear tools cache so it regenerates
            self._tools_cache = None
            
            logger.info(f"✅ Registered A2A agent: {name} ({base_url})")
        except Exception as e:
            logger.error(f"❌ Failed to register agent {name} at {base_url}: {e}")
            # Depending on robustness requirements, we might want to re-raise or just log error
            # For now, we'll log it and continue, but the agent won't be available.
    
    async def register_agents_from_file(self, file_path: str):
        """Register multiple agents from a Registry JSON file"""
        logger.info(f"Loading agent registry from {file_path}")
        if not os.path.exists(file_path):
            logger.warning(f"⚠️ Registry file not found at {file_path}. Skipping.")
            return

        try:
            with open(file_path, 'r') as f:
                registry = json.load(f)
            
            for name, url in registry.items():
                await self.register_remote_agent(name, url)
                
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse registry file: {e}")
        except Exception as e:
            logger.error(f"❌ Error loading registry: {e}")

    @property
    def tools(self):
        """Generate tools for communicating with registered agents"""
        
        if self._tools_cache is None:
            self._tools_cache = []
            logger.info("Generating tools for registered remote agents...")
            
            for agent_name, client in self.remote_agents.items():
                
                # Check if client has successfully discovered agent card
                if not client.agent_card:
                     logger.warning(f"⚠️ Skipping tool generation for {agent_name} - Agent card not available (discovery failed?)")
                     continue

                def make_tool(name: str, client_obj: A2AHTTPClient):
                    agent_card = client_obj.agent_card
                    capabilities = agent_card.get('capabilities', [])
                    description = agent_card.get('description', 'No description provided')

                    # Build the tool description dynamically
                    tool_description = f"""Send a task to {name} via A2A protocol.

Agent: {agent_card.get('name')}
Description: {description}
Capabilities: {', '.join(capabilities)}"""

                    def communicate_func(query: str) -> str:
                        """Communicate with the remote agent"""
                        logger.info(f"🔧 Tool 'communicate_with_{name}' invoked with query: {query[:50]}...")
                        # Run async code in sync context
                        try:
                            loop = asyncio.get_event_loop()
                        except RuntimeError:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)

                        try:
                            result = loop.run_until_complete(
                                client_obj.send_message(query)
                            )

                            # Extract response from result
                            task = result.get("task", {})
                            messages = task.get("messages", [])

                            if messages and len(messages) > 1:
                                last_message = messages[-1]
                                parts = last_message.get("parts", [])
                                if parts:
                                    response_content = parts[0].get("content", "No response")
                                    logger.info(f"   Response received from {name}: {response_content[:50]}...")
                                    return response_content

                            logger.warning(f"   No content in response from {name}")
                            return "No response received"
                        except Exception as e:
                            logger.error(f"   Error communicating with {name}: {e}")
                            return f"Error communicating with agent: {str(e)}"

                    # Create structured tool with custom name and description
                    tool_name = f"communicate_with_{name.replace('-', '_')}"
                    return StructuredTool.from_function(
                        func=communicate_func,
                        name=tool_name,
                        description=tool_description
                    )
                
                tool_func = make_tool(agent_name, client)
                self._tools_cache.append(tool_func)
                logger.info(f"   Created tool: communicate_with_{agent_name.replace('-', '_')}")
        
        return self._tools_cache
    
    async def cleanup(self):
        """Close all HTTP clients"""
        logger.info("Cleaning up A2A middleware...")
        for client in self.remote_agents.values():
            await client.close()
