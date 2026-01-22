
import asyncio
import json
import uuid
from typing import Dict, Any, Optional, List
import httpx
from datetime import datetime
import logging

# Configure logging
logger = logging.getLogger(__name__)

class A2AHTTPClient:
    """Real HTTP client for A2A protocol communication"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.agent_card: Optional[Dict[str, Any]] = None
        self.client = httpx.AsyncClient(timeout=30.0)
    
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
        """Send message via A2A message/send JSON-RPC method"""
        
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
        
        try:
            endpoint = self.agent_card.get('endpoint') if self.agent_card else f"{self.base_url}/a2a"
            logger.info(f"📤 Sending message to {self.agent_card.get('name', 'agent') if self.agent_card else self.base_url }...")
            logger.debug(f"   Content: {content[:100]}...")
            
            response = await self.client.post(
                endpoint,
                json=request_payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"📥 Received response from {self.agent_card.get('name', 'agent') if self.agent_card else self.base_url}")
            
            return result.get("result", {})
            
        except httpx.HTTPError as e:
            logger.error(f"❌ Failed to send message: {e}")
            raise
    
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
