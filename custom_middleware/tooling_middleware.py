from typing import Set, List
from langchain_core.tools import tool
from langchain.agents.middleware import AgentMiddleware
from deepagents import create_deep_agent

class DynamicMCPToolLoader:
    def __init__(self):
        self.mcp_servers = {
            "email": MCPClient("gmail-server"),
            "storage": MCPClient("gdrive-server"),
            "communication": MCPClient("slack-server"),
        }
        self.tool_registry = {}  # name -> tool mapping
        self.category_map = {}   # category -> [tool_names]
        self.loaded_categories = set()
        
    async def load_category(self, category: str) -> List[str]:
        """Load tools from MCP and return tool names"""
        if category in self.category_map:
            return self.category_map[category]
            
        mcp_client = self.mcp_servers[category]
        await mcp_client.connect()
        
        mcp_tools = await mcp_client.list_tools()
        tool_names = []
        
        for mcp_tool in mcp_tools:
            langchain_tool = convert_mcp_to_langchain(mcp_tool, mcp_client)
            self.tool_registry[langchain_tool.name] = langchain_tool
            tool_names.append(langchain_tool.name)
        
        self.category_map[category] = tool_names
        self.loaded_categories.add(category)
        return tool_names

# Global loader instance
loader = DynamicMCPToolLoader()

@tool
def tools_discover(query: str) -> str:
    """Search for available tool categories.
    Use when you need capabilities not currently loaded.
    """
    results = {
        "email": "Gmail operations - search, read, send emails",
        "storage": "Google Drive - upload, download, search files",
        "communication": "Slack - send messages, read channels",
    }
    
    matches = {k: v for k, v in results.items() if query.lower() in k or query.lower() in v.lower()}
    return f"Available categories: {matches}"

@tool
async def tools_load(categories: List[str]) -> str:
    """Load additional tool categories into your available tools.
    After calling this, you'll have access to new tools in those categories.
    
    Args:
        categories: List of category names to load (e.g., ["email", "storage"])
    """
    newly_loaded = []
    for category in categories:
        tool_names = await loader.load_category(category)
        newly_loaded.extend(tool_names)
    
    return f"Loaded {len(newly_loaded)} tools from categories {categories}. " \
           f"You can now use: {newly_loaded}"

class DynamicToolMiddleware(AgentMiddleware):
    """Middleware that dynamically provides tools based on what's been loaded"""
    
    @property
    def tools(self):
        """Return all loaded tools + core management tools"""
        loaded_tools = [loader.tool_registry[name] for name in loader.tool_registry]
        return [tools_discover, tools_load] + loaded_tools
    
    def wrap_model_call(self, model_call):
        """Ensure model always sees current tool set"""
        async def wrapped(*args, **kwargs):
            # The @property tools will be evaluated fresh each time
            # giving the model the latest tool set
            return await model_call(*args, **kwargs)
        return wrapped

