"""
Recursive Language Model (RLM) Middleware for LangChain/DeepAgents
Based on "Recursive Language Models" (arXiv:2512.24601)

This middleware enables agents to handle arbitrarily long contexts
by treating them as external environment data that can be programmatically
inspected and recursively processed.
"""

from typing import Any, Dict, List, Optional, Union, Callable
import json
import re
import sys
import traceback
from io import StringIO
from dataclasses import dataclass

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from langchain_core.tools import tool, BaseTool, StructuredTool
from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models import BaseChatModel


@dataclass
class RLMConfig:
    """Configuration for RLM behavior."""
    max_recursion_depth: int = 1
    max_iterations: int = 20
    context_chunk_size: int = 100000
    enable_sub_calls: bool = True
    truncate_output_chars: int = 5000
    execution_timeout: int = 30


class REPLEnvironment:
    """
    A safe Python REPL environment for RLM operations.
    Manages context variables and provides LLM query capability.
    """
    
    def __init__(self, context: Union[str, Dict, List] = "", llm_query_fn: Optional[Callable] = None):
        self.globals = {
            'context': context,
            'json': json,
            're': re,
            '__builtins__': __builtins__,
        }
        self.locals = {}
        self.output_buffer = StringIO()
        
        if llm_query_fn:
            self.globals['llm_query'] = llm_query_fn
            
    def set_context(self, context: Union[str, Dict, List]):
        """Update the context variable."""
        self.globals['context'] = context
    
    def execute(self, code: str) -> Dict[str, Any]:
        """
        Execute Python code in the REPL environment.
        """
        # Redirect stdout
        old_stdout = sys.stdout
        sys.stdout = self.output_buffer
        
        result = {
            'success': False,
            'output': '',
            'error': None,
            'variables': {}
        }
        
        try:
            # Execute the code
            # Note: In a real sandboxed environment, this should be more restricted.
            exec(code, self.globals, self.locals)
            
            # Capture output
            sys.stdout = old_stdout
            output = self.output_buffer.getvalue()
            
            # Get relevant variables (excluding builtins and modules)
            variables = {
                k: str(v)[:200] + '...' if len(str(v)) > 200 else str(v)
                for k, v in self.locals.items()
                if not k.startswith('_') and k not in ['json', 're']
            }
            
            result['success'] = True
            result['output'] = output
            result['variables'] = variables
            
        except Exception as e:
            sys.stdout = old_stdout
            result['error'] = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
            result['output'] = self.output_buffer.getvalue()
        
        finally:
            # Reset buffer for next execution
            self.output_buffer = StringIO()
            sys.stdout = old_stdout
        
        return result
    
    def get_context_info(self) -> Dict[str, Any]:
        """Get information about the context."""
        context = self.globals.get('context')
        
        info = {
            'type': type(context).__name__,
        }
        
        if isinstance(context, str):
            info['total_chars'] = len(context)
            info['total_lines'] = context.count('\n') + 1
        elif isinstance(context, (list, dict)):
            info['length'] = len(context)
            if isinstance(context, list) and context:
                info['item_type'] = type(context[0]).__name__
        
        return info


class RLMMiddleware(AgentMiddleware):
    """
    Middleware that equips an agent with RLM capabilities:
    1. A REPL environment to inspect 'context'.
    2. Sub-LLM query tools for recursive processing.
    3. Utilities to load data into the context.
    """
    
    def __init__(
        self,
        model: BaseChatModel,
        config: Optional[RLMConfig] = None,
        initial_context: Union[str, Dict, List, Any] = ""
    ):
        """
        Initialize RLM Middleware.
        
        Args:
            model: The LLM to use for recursive sub-calls (llm_query).
            config: Configuration for RLM.
            initial_context: Initial data to load into the RLM context variable.
        """
        super().__init__()
        self.model = model
        self.config = config or RLMConfig()
        self.current_depth = 0
        
        # Initialize REPL
        self.env = REPLEnvironment(
            context=initial_context,
            llm_query_fn=self._llm_query_impl if self.config.enable_sub_calls else None
        )
        
    def _llm_query_impl(self, prompt: str) -> str:
        """Internal implementation of llm_query."""
        if self.current_depth >= self.config.max_recursion_depth:
            return "ERROR: Maximum recursion depth reached. Cannot make more sub-LLM calls."
        
        self.current_depth += 1
        try:
            # Sub-call to the model
            messages = [HumanMessage(content=prompt)]
            response = self.model.invoke(messages)
            result = response.content
        except Exception as e:
            result = f"ERROR in llm_query: {str(e)}"
        finally:
            self.current_depth -= 1
            
        return str(result)

    @property
    def tools(self) -> List[BaseTool]:
        """Return the RLM tools provided to the agent."""
        return [
            self._create_load_context_tool(),
            self._create_repl_tool(),
            self._create_context_info_tool(),
            # self._create_llm_query_tool() # Optional: Expose directly as tool too?
        ]

    @property
    def system_prompt(self) -> str:
        """Return the RLM usage instructions."""
        context_info = self.env.get_context_info()
        
        sub_call_instructions = ""
        if self.config.enable_sub_calls:
            sub_call_instructions = """
    - 'llm_query(prompt)': Available inside the REPL to query a sub-LLM.
      Use this for semantic processing of text chunks (e.g. "Summarize this chunk").
"""

        return f"""
## RLM (Recursive Language Model) Capabilities
You have access to a persistent Python REPL environment to handle large contexts/data.

Environment properties:
- Variable 'context': currently holds data of type {context_info.get('type')} (Length: {context_info.get('total_chars', context_info.get('length', 'N/A'))})
- Module 'json', 're': Available for data processing.
{sub_call_instructions}

Tools:
1. `rlm_execute_code`: Run Python code to inspect 'context', filter data, or aggregate results.
2. `rlm_load_context`: Load new data into the 'context' variable (e.g. from a file or network response).
3. `rlm_context_info`: Refresh your knowledge of the current context structure.

Best Practices:
- Do not dump large contexts directly to output.
- Use code to filter/search first.
- Use `llm_query` within code loops to process chunks semantically.
"""

    def _create_load_context_tool(self) -> BaseTool:
        def load_context_func(data: str) -> str:
            """Load data into the RLM 'context' variable."""
            # Attempt to parse as JSON if possible for better structure
            try:
                parsed = json.loads(data)
                self.env.set_context(parsed)
                return "Context loaded as JSON/Dict."
            except:
                self.env.set_context(data)
                return "Context loaded as String."

        return StructuredTool.from_function(
            func=load_context_func,
            name="rlm_load_context",
            description="Load text or JSON data into the global 'context' variable for inspection."
        )

    def _create_repl_tool(self) -> BaseTool:
        def repl_func(code: str) -> str:
            """Execute Python code in the RLM environment."""
            result = self.env.execute(code)
            if result['success']:
                output = result['output']
                if len(output) > self.config.truncate_output_chars:
                    output = output[:self.config.truncate_output_chars] + f"\n... (truncated)"
                return f"Output:\n{output}\nVariables created: {list(result['variables'].keys())}"
            else:
                return f"Error:\n{result['error']}"
        
        return StructuredTool.from_function(
            func=repl_func,
            name="rlm_execute_code",
            description="Execute Python code to inspect 'context' or process data. You can call `llm_query(prompt)` inside the code."
        )
    
    def _create_context_info_tool(self) -> BaseTool:
        def info_func() -> str:
            """Get info about current context."""
            return str(self.env.get_context_info())
            
        return StructuredTool.from_function(
            func=info_func,
            name="rlm_context_info",
            description="Get information about the current data in 'context' (type, size)."
        )
