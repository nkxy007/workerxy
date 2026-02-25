from typing import List, Dict, Any, Optional
from langchain_core.tools import BaseTool
import asyncio
from rich.prompt import Prompt

class SecurityManager:
    """
    Manages security policies for tool execution.
    Handles user approval for sensitive tools.
    """
    
    def __init__(self, ui_callback=None):
        self.always_allow: List[str] = [] # List of tool names that are always allowed
        self.session_allowlist: List[str] = [] # List of specific commands allowed for this session
        self.ui_callback = ui_callback
        

    async def check_approval(self, tool_name: str, args: Dict[str, Any]) -> bool:
        """
        Check if a tool execution is approved.
        Returns True if approved, False if denied.
        """
        # 1. Check if tool is always allowed
        if tool_name in self.always_allow:
            return True
            
        # 2. Check specific command signature (not fully implemented yet, but good for future)
        # signature = f"{tool_name}:{args}"
        # if signature in self.session_allowlist:
        #     return True
            
        # 3. If no callback, default to identifying as unsafe if it's a sensitive tool
        # For now, we assume ALL tools passing through here are sensitive
        if not self.ui_callback:
            return False
            
        # 4. Request user approval
        choice = await self.ui_callback(tool_name, args)
        
        if choice == "allow_once":
            return True
        elif choice == "allow_all":
            self.always_allow.append(tool_name)
            return True
        else:
            return False

class SensitiveToolWrapper(BaseTool):
    """
    Wraps a BaseTool to add security checks before execution.
    """
    name: str
    description: str
    original_tool: BaseTool
    security_manager: SecurityManager
    
    
    def __init__(self, original_tool: BaseTool, security_manager: SecurityManager):
        super().__init__(
            name=original_tool.name,
            description=original_tool.description,
            args_schema=original_tool.args_schema,
            original_tool=original_tool,
            security_manager=security_manager
        )
        
    def _run(self, *args, **kwargs) -> Any:
        """Synchronous execution"""
        # Combine args and kwargs for display
        tool_args = kwargs.copy()
        if args:
            tool_args["args"] = args
            
        # Note: In a pure async CLI, this sync path might be reached if not careful.
        # But we mostly use _arun.
        # For now, this will fail if it tries to await an async callback from sync code.
        # We'll keep it simple for now since we primarily use async.
        return "Error: Sync tool execution not supported when async approval is required."
            
    async def _arun(self, *args, **kwargs) -> Any:
        """Asynchronous execution"""
        tool_args = kwargs.copy()
        if args:
            tool_args["args"] = args
            
        # Use await directly since check_approval is now async
        approved = await self.security_manager.check_approval(self.name, tool_args)
        
        if approved:
            # Use ainvoke instead of _arun to ensure config and other parameters are handled correctly
            # by the framework, especially for StructuredTools that might require 'config'.
            return await self.original_tool.ainvoke(kwargs)
        else:
            return "Error: Tool execution denied by user."

