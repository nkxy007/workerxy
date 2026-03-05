
import asyncio
import json
import uuid
from typing import Dict, Any, Optional, List
import httpx
from datetime import datetime
from net_deepagent_cli.communication.logger import setup_logger

# Configure logging using centralized utility
logger = setup_logger("a2a_client")

class A2AHTTPClient:
    """Real HTTP client for A2A protocol communication"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.agent_card: Optional[Dict[str, Any]] = None
        # Increase read timeout for long-running agent tasks, but keep connect timeout short
        # to fail fast if the agent is unreachable.
        timeout = httpx.Timeout(30.0, connect=10.0)
        self.client = httpx.AsyncClient(timeout=timeout)
    
    async def discover_agent(self) -> Dict[str, Any]:
        """Discover agent by fetching its Agent Card"""
        
        try:
            card_url = f"{self.base_url}/.well-known/agent.json"
            logger.info(f"🔍 Discovering agent at {card_url}")
            
            response = await self.client.get(card_url)
            response.raise_for_status()
            
            self.agent_card = response.json()
            logger.info(f"✅ Discovered: {self.agent_card.get('name')}")
            logger.debug(f"   Capabilities: {', '.join(self.agent_card.get('capabilities', []))}")
            
            return self.agent_card
            
        except httpx.HTTPError as e:
            logger.error(f"❌ Failed to discover agent: {e}")
            raise
    
    async def send_message(
        self,
        content: str,
        task_id: Optional[str] = None,
        context_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send message via A2A message/send JSON-RPC method, with polling fallback"""
        
        # Generate IDs if not provided
        task_id = task_id or str(uuid.uuid4())
        context_id = context_id or str(uuid.uuid4())
        
        # Construct JSON-RPC request
        request_payload = {
            "jsonrpc": "2.0",
            "method": "message/send",
            "id": str(uuid.uuid4()),
            "params": {
                "task_id": task_id,
                "context_id": context_id,
                "message": {
                    "role": "user",
                    "parts": [
                        {
                            "type": "text",
                            "content": content
                        }
                    ],
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        }
        
        endpoint = self.agent_card.get('endpoint') if self.agent_card else f"{self.base_url}/a2a"
        agent_name = self.agent_card.get('name', 'agent') if self.agent_card else self.base_url
        
        try:
            logger.info(f"📤 Sending message to {agent_name}...")
            logger.debug(f"   Content: {content[:100]}...")
            
            response = await self.client.post(
                endpoint,
                json=request_payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"📥 Received response from {agent_name}")
            return result.get("result", {})
            
        except httpx.ReadTimeout:
            logger.warning(f"⏱️  Request to {agent_name} timed out. Switching to polling mode for Task ID: {task_id}")
            return await self._poll_for_completion(task_id, agent_name)
            
        except httpx.HTTPError as e:
            logger.error(f"❌ Failed to send message: {e}")
            raise

    async def _poll_for_completion(self, task_id: str, agent_name: str, max_attempts: int = 100, interval: float = 3.0) -> Dict[str, Any]:
        """Poll for task completion"""
        logger.info(f"🔄 Polling {agent_name} for task {task_id}...")
        
        for attempt in range(max_attempts):
            try:
                # Wait before polling
                await asyncio.sleep(interval)
                
                # Get task status
                # Note: get_task returns the "result" part of the JSON-RPC response, 
                # which contains the "task" object
                result = await self.get_task(task_id)
                task = result.get("task", {})
                status = task.get("status")
                
                if status == "completed":
                    logger.info(f"✅ Polling successful: Task {task_id} completed.")
                    # Return the full result structure expected by the caller 
                    # (which usually expects the JSON-RPC 'result' object containing the 'task')
                    return result
                
                elif status == "failed":
                    error_msg = "Unknown error"
                    # Try to find error artifact
                    for artifact in task.get("artifacts", []):
                        if artifact.get("type") == "error":
                            error_msg = artifact.get("content")
                    
                    logger.error(f"❌ Task {task_id} failed on remote agent: {error_msg}")
                    raise Exception(f"Remote agent task failed: {error_msg}")
                
                elif attempt % 5 == 0:
                    logger.info(f"   ... still waiting for {agent_name} (status: {status})")
                    
            except Exception as e:
                # If polling itself fails (e.g. connection error), log and continue (maybe intermittent)
                logger.warning(f"⚠️  Polling error (attempt {attempt+1}/{max_attempts}): {e}")
        
        raise Exception(f"Task {task_id} timed out after polling {max_attempts} times.")
    
    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """Retrieve task status via A2A tasks/get JSON-RPC method"""
        
        request_payload = {
            "jsonrpc": "2.0",
            "method": "tasks/get",
            "id": str(uuid.uuid4()),
            "params": {
                "task_id": task_id
            }
        }
        
        try:
            endpoint = self.agent_card.get('endpoint') if self.agent_card else f"{self.base_url}/a2a"
            
            response = await self.client.post(
                endpoint,
                json=request_payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            result = response.json()
            return result.get("result", {})
            
        except httpx.HTTPError as e:
            logger.error(f"❌ Failed to get task: {e}")
            raise
    
    async def stream_message(
        self,
        content: str,
        task_id: Optional[str] = None,
        context_id: Optional[str] = None
    ):
        """Stream message response via A2A message/stream JSON-RPC method with SSE"""
        
        task_id = task_id or str(uuid.uuid4())
        context_id = context_id or str(uuid.uuid4())
        
        request_payload = {
            "jsonrpc": "2.0",
            "method": "message/stream",
            "id": str(uuid.uuid4()),
            "params": {
                "task_id": task_id,
                "context_id": context_id,
                "message": {
                    "role": "user",
                    "parts": [{"type": "text", "content": content}],
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        }
        
        endpoint = self.agent_card.get('endpoint') if self.agent_card else f"{self.base_url}/a2a"
        
        async with self.client.stream(
            "POST",
            endpoint,
            json=request_payload,
            headers={"Content-Type": "application/json"}
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    yield data
    
    async def close(self):
        """Close HTTP client"""
        logger.info(f"Closing client for {self.base_url}")
        await self.client.aclose()
