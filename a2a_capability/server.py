import asyncio
import json
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
import uvicorn

from langchain_core.messages import HumanMessage, AIMessage
from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
import sys 
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from utils.credentials_helper import get_credential, get_helper
from net_deepagent_cli.communication.logger import setup_logger

# Initialize credentials
get_helper()

# Configure logging for visibility using centralized utility
logger = setup_logger("a2a_server")

# ============================================================================
# A2A Data Models (Pydantic)
# ============================================================================

class TextPart(BaseModel):
    """A2A text message part"""
    type: str = "text"
    content: str


class Message(BaseModel):
    """A2A message"""
    role: str  # "user" or "agent"
    parts: List[TextPart]
    timestamp: Optional[str] = None


class MessageSendRequest(BaseModel):
    """A2A message/send JSON-RPC request"""
    jsonrpc: str = "2.0"
    method: str = "message/send"
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    params: Dict[str, Any] = Field(
        default_factory=lambda: {
            "task_id": str(uuid.uuid4()),
            "context_id": str(uuid.uuid4()),
            "message": {
                "role": "user",
                "parts": [{"type": "text", "content": ""}]
            }
        }
    )


class Task(BaseModel):
    """A2A task object"""
    task_id: str
    context_id: str
    status: str  # "submitted", "working", "completed", "failed"
    messages: List[Message] = Field(default_factory=list)
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class AgentCard(BaseModel):
    """A2A Agent Card for discovery"""
    name: str
    description: str
    version: str = "1.0.0"
    endpoint: str
    capabilities: List[str] = Field(default_factory=list)
    supported_modalities: List[str] = Field(default_factory=lambda: ["text"])
    authentication: Dict[str, Any] = Field(
        default_factory=lambda: {"type": "none"}
    )


# ============================================================================
# A2A Server Implementation
# ============================================================================

class A2AServer:
    """Full-featured A2A server implementation"""
    
    def __init__(
        self,
        agent_name: str,
        agent_description: str,
        agent_capabilities: List[str],
        agent_instance: Any = None, # Allow passing in an existing agent instance
        model_name: str = "gpt-5-mini", # fallback model
        claude_model_name: str = "claude-4"
    ):
        self.agent_name = agent_name
        self.agent_description = agent_description
        self.agent_capabilities = agent_capabilities
        
        # Initialize the DeepAgent or use provided one
        if agent_instance:
            self.agent = agent_instance
            logger.info(f"Initialized A2AServer '{agent_name}' with injected agent instance.")
        else:
            logger.info(f"Initializing A2AServer '{agent_name}' with new DeepAgent (model={model_name})")
            # Fallback to creating a simple one if not provided
            try:
                 self.model = ChatOpenAI(model=model_name, api_key=get_credential("OPENAI_KEY"))
            except:
                 # Fallback for demo if credentials missing for OpenAI
                 logger.warning("Could not init OpenAI, trying Anthropic...")
                 self.model = ChatAnthropic(model=claude_model_name, api_key=get_credential("ANTHROPIC_KEY"))

            self.agent = create_deep_agent(
                model=self.model,
                system_prompt=f"""You are {agent_name}, a specialized AI agent.
    
    Your capabilities: {', '.join(agent_capabilities)}
    
    Your role: {agent_description}
    
    Provide helpful, accurate, and specialized assistance in your area of expertise."""
            )
        
        # Task storage
        self.tasks: Dict[str, Task] = {}
        
        # Agent card
        self.agent_card = AgentCard(
            name=agent_name,
            description=agent_description,
            endpoint="",  # Will be set when server starts
            capabilities=agent_capabilities
        )
    
    def create_agent_card(self, base_url: str) -> Dict[str, Any]:
        """Create agent card with proper endpoint"""
        self.agent_card.endpoint = f"{base_url}/a2a"
        return self.agent_card.model_dump()
    
    async def handle_message_send(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle A2A message/send JSON-RPC method"""
        
        # Extract parameters
        params = request_data.get("params", {})
        task_id = params.get("task_id", str(uuid.uuid4()))
        context_id = params.get("context_id", str(uuid.uuid4()))
        message_data = params.get("message", {})
        
        # Parse incoming message
        incoming_message = Message(**message_data)
        
        # Extract content
        content = ""
        if incoming_message.parts:
            content = incoming_message.parts[0].content
        
        logger.info(f"📨 [{self.agent_name}] Received task {task_id}: {content[:60]}...")
        
        # Create or retrieve task
        if task_id not in self.tasks:
            task = Task(
                task_id=task_id,
                context_id=context_id,
                status="working",
                messages=[incoming_message]
            )
            self.tasks[task_id] = task
        else:
            task = self.tasks[task_id]
            task.messages.append(incoming_message)
            task.status = "working"
        
        # Process with DeepAgent
        try:
            # We call invoke on the agent.
            # Note: net_deepagent expects {"messages": ...} usually
            logger.info(f"⚙️  [{self.agent_name}] Processing...")
            result = await self.agent.ainvoke({
                "messages": [{"role": "user", "content": content}]
            })
            
            # Extract response
            # Result from DeepAgent usually has "messages" key where last is AIMessage
            if isinstance(result, dict) and "messages" in result:
                response_content = result["messages"][-1].content
            else:
                # Fallback if result format differs
                response_content = str(result)
            
            logger.info(f"✅ [{self.agent_name}] Completed task {task_id}")
            
            # Create response message
            response_message = Message(
                role="agent",
                parts=[TextPart(type="text", content=response_content)],
                timestamp=datetime.utcnow().isoformat()
            )
            
            # Update task
            task.messages.append(response_message)
            task.status = "completed"
            task.updated_at = datetime.utcnow().isoformat()
            
            # Create artifact (optional but good for A2A)
            task.artifacts.append({
                "type": "result",
                "content": response_content,
                "timestamp": datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            logger.error(f"❌ [{self.agent_name}] Task {task_id} failed: {e}", exc_info=True)
            task.status = "failed"
            task.artifacts.append({
                "type": "error",
                "content": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })
        
        # Return JSON-RPC response
        return {
            "jsonrpc": "2.0",
            "id": request_data.get("id"),
            "result": {
                "task": task.model_dump()
            }
        }
    
    async def handle_task_get(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle A2A tasks/get JSON-RPC method"""
        
        params = request_data.get("params", {})
        task_id = params.get("task_id")
        
        if not task_id or task_id not in self.tasks:
            return {
                "jsonrpc": "2.0",
                "id": request_data.get("id"),
                "error": {
                    "code": -32602,
                    "message": "Task not found"
                }
            }
        
        task = self.tasks[task_id]
        return {
            "jsonrpc": "2.0",
            "id": request_data.get("id"),
            "result": {
                "task": task.model_dump()
            }
        }
    
    async def handle_message_stream(self, request_data: Dict[str, Any]):
        """Handle A2A message/stream JSON-RPC method with SSE"""
        
        return {
             "jsonrpc": "2.0",
             "error": {"code": -32000, "message": "Streaming not fully implemented in this demo version"}
        }

# ============================================================================
# FastAPI Application Factory
# ============================================================================

def create_a2a_app(
    agent_name: str,
    agent_description: str,
    agent_capabilities: List[str],
    port: int = 8000,
    agent_instance: Any = None
) -> FastAPI:
    """Create a FastAPI application with A2A endpoints"""
    
    # Lifecycle management
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
        logger.info(f"🚀 Starting A2A Server: {agent_name}")
        logger.info(f"📡 Endpoint: http://localhost:{port}/a2a")
        logger.info(f"🔍 Agent Card: http://localhost:{port}/.well-known/agent.json")
        yield
        # Shutdown
        logger.info(f"🛑 Shutting down A2A Server: {agent_name}")
    
    app = FastAPI(
        title=f"{agent_name} - A2A Server",
        description=agent_description,
        version="1.0.0",
        lifespan=lifespan
    )
    
    # Initialize A2A server
    a2a_server = A2AServer(
        agent_name=agent_name,
        agent_description=agent_description,
        agent_capabilities=agent_capabilities,
        agent_instance=agent_instance
    )
    
    @app.get("/.well-known/agent.json")
    async def get_agent_card():
        """A2A Agent Discovery Endpoint"""
        base_url = f"http://localhost:{port}"
        return JSONResponse(content=a2a_server.create_agent_card(base_url))
    
    @app.post("/a2a")
    async def a2a_endpoint(request: Request):
        """Main A2A JSON-RPC endpoint"""
        
        try:
            request_data = await request.json()
            method = request_data.get("method")
            
            if method == "message/send":
                response = await a2a_server.handle_message_send(request_data)
                return JSONResponse(content=response)
            
            elif method == "message/stream":
                # Implementation simplified for now
                response = await a2a_server.handle_message_stream(request_data)
                return JSONResponse(content=response)
            
            elif method == "tasks/get":
                response = await a2a_server.handle_task_get(request_data)
                return JSONResponse(content=response)
            
            else:
                return JSONResponse(
                    content={
                        "jsonrpc": "2.0",
                        "id": request_data.get("id"),
                        "error": {
                            "code": -32601,
                            "message": f"Method not found: {method}"
                        }
                    },
                    status_code=400
                )
        
        except Exception as e:
            logger.error(f"Internal error processing request: {e}", exc_info=True)
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32603,
                        "message": f"Internal error: {str(e)}"
                    }
                },
                status_code=500
            )
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {"status": "healthy", "agent": agent_name}
    
    return app

