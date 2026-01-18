from typing import Optional, List, Dict, Any
from pathlib import Path
import yaml
import asyncio
from net_deepagent import create_network_agent

class AgentMemoryMiddleware:
    """Load and inject agent memory from ~/.net-deepagent/<agent_name>/agent.md"""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.memory_dir = Path.home() / ".net-deepagent" / agent_name
        self.memory_file = self.memory_dir / "agent.md"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
    async def __call__(self, state: Dict[str, Any]):
        # Load memory if exists
        if self.memory_file.exists():
            memory_content = self.memory_file.read_text()
            memory_text = f"\n\n## Agent Memory\n{memory_content}"
            
            # 1. Inject into system_prompt if it exists
            if "system_prompt" in state:
                state["system_prompt"] = f"{state.get('system_prompt', '')}{memory_text}"
            
            # 2. Also inject as a SystemMessage if messages exist
            if "messages" in state and isinstance(state["messages"], list):
                from langchain_core.messages import SystemMessage
                # Prepend or check if system message already exists
                # For simplicity, we'll prepend a new one
                state["messages"] = [SystemMessage(content=f"Background Context: {memory_text}")] + state["messages"]
        return state

class SkillsMiddleware:
    """Progressive disclosure skills system"""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.skills_dir = Path.home() / ".net-deepagent" / agent_name / "skills"
        self.project_skills_dir = Path.cwd() / ".net-deepagent" / "skills"
        self.hard_coded_skills = Path.cwd() /"skills"
        print("*"*70)
        print(f"{self.hard_coded_skills}")
        print("*"*70)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        
    def scan_skills(self):
        """Scan for available skills and extract metadata"""
        skills = []
        
        for s_dir in [self.skills_dir, self.project_skills_dir, self.hard_coded_skills]:
            if not s_dir.exists():
                continue
                
            for skill_path in s_dir.glob("**/SKILL.md"):
                metadata = self.parse_skill_metadata(skill_path)
                skills.append({
                    "name": metadata.get("name", skill_path.parent.name),
                    "description": metadata.get("description", "No description provided"),
                    "path": str(skill_path)
                })
        
        return skills
    
    def parse_skill_metadata(self, skill_path: Path):
        """Parse YAML frontmatter from SKILL.md"""
        try:
            content = skill_path.read_text()
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    return yaml.safe_load(parts[1]) or {}
        except Exception:
            pass
        return {}
    
    async def __call__(self, state: Dict[str, Any]):
        """Inject skill list into system prompt or messages"""
        skills = self.scan_skills()
        
        if skills:
            skills_text = "## Available Skills\n\n"
            for skill in skills:
                skills_text += f"- **{skill['name']}**: {skill['description']} (Path: {skill['path']}\n"
            skills_text += "\nTo use a skill, read its full instructions with the appropriate tool (e.g., read_file or similar).\n"
            
            # 1. Inject into system_prompt if it exists
            if "system_prompt" in state:
                state["system_prompt"] = f"{state.get('system_prompt', '')}\n\n{skills_text}"
            
            # 2. Also inject as a SystemMessage if messages exist
            if "messages" in state and isinstance(state["messages"], list):
                from langchain_core.messages import SystemMessage
                state["messages"] = [SystemMessage(content=skills_text)] + state["messages"]
        
        return state

class WrappedAgent:
    """Wrapper for the agent to apply middleware and handle streaming"""
    
    def __init__(self, base_agent, middlewares: List[Any]):
        self.base_agent = base_agent
        self.middlewares = middlewares
        
    async def astream(self, input_data: Dict[str, Any], **kwargs):
        # Apply middlewares before calling the agent
        state = input_data.copy()
        for middleware in self.middlewares:
            state = await middleware(state)
            
        # Call the base agent's astream
        async for chunk in self.base_agent.astream(state, **kwargs):
            yield chunk

    async def ainvoke(self, input_data: Dict[str, Any], **kwargs):
        state = input_data.copy()
        for middleware in self.middlewares:
            state = await middleware(state)
        return await self.base_agent.ainvoke(state, **kwargs)

async def create_cli_agent(
    agent_name: str,
    mcp_server_url: str,
    main_model_name: str,
    subagent_model_name: str,
    design_model_name: str,
    auto_approve: bool = False
):
    """Create agent with CLI-specific middleware"""
    
    # Create base agent using the existing function from net_deepagent
    base_agent = await create_network_agent(
        mcp_server_url=mcp_server_url,
        main_model_name=main_model_name,
        subagent_model_name=subagent_model_name,
        design_model_name=design_model_name
    )
    
    # Initialize middleware
    memory_middleware = AgentMemoryMiddleware(agent_name)
    skills_middleware = SkillsMiddleware(agent_name)
    
    # Wrap agent with middleware
    wrapped_agent = WrappedAgent(base_agent, [
        memory_middleware,
        skills_middleware
    ])
    
    return wrapped_agent
