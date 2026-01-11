from pathlib import Path
from typing import Optional
import yaml
import os

class AgentConfig:
    """Manage agent configuration"""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.config_dir = Path.home() / ".net-deepagent" / agent_name
        self.config_file = self.config_dir / "config.yaml"
        
        # Create directories
        self.config_dir.mkdir(parents=True, exist_ok=True)
        (self.config_dir / "skills").mkdir(exist_ok=True)
        (self.config_dir / "memories").mkdir(exist_ok=True)
    
    def load_config(self) -> dict:
        """Load agent configuration"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return yaml.safe_load(f)
            except Exception:
                return self.default_config()
        return self.default_config()
    
    def save_config(self, config: dict):
        """Save agent configuration"""
        with open(self.config_file, 'w') as f:
            yaml.dump(config, f)
    
    def default_config(self) -> dict:
        """Default configuration"""
        return {
            "agent_name": self.agent_name,
            "main_model": "gpt-5-mini",
            "subagent_model": "gpt-5-mini-minimal",
            "design_model": "gpt-4.1",
            "mcp_server": "http://localhost:8000/mcp",
            "auto_approve": False
        }

def find_project_root() -> Optional[Path]:
    """Find project root by looking for .git or .python-version or similar markers"""
    current = Path.cwd()
    
    while current != current.parent:
        if (current / ".git").exists() or (current / ".python-version").exists() or (current / "pyproject.toml").exists():
            return current
        current = current.parent
    
    return None
