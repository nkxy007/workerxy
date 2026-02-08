"""
Recursive Language Model (RLM) Middleware for LangChain/DeepAgents
Based on "Recursive Language Models" (arXiv:2512.24601)

This middleware enables agents to handle arbitrarily long contexts
by treating them as external environment data that can be programmatically
inspected and recursively processed.

Architecture:
- Tools-first approach: Agent has full autonomy
- Transparent handling of large tool outputs via wrap_model_call
- Persistent REPL environment throughout conversation
- Automatic system prompt injection via before_model hook
"""

from typing import Any, Dict, List, Optional, Union, Callable
import json
import re
import sys
import traceback
from io import StringIO
from dataclasses import dataclass
import logging

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)


@dataclass
class RLMConfig:
    """Configuration for RLM behavior."""
    max_recursion_depth: int = 1
    max_iterations: int = 50  # Higher for complex network analysis
    enable_sub_calls: bool = True
    truncate_output_chars: int = 5000
    large_output_threshold: int = 50000  # 50KB threshold for auto-offloading
    context_preview_chars: int = 500  # Preview size when offloading


class REPLEnvironment:
    """
    A safe Python REPL environment for RLM operations.
    Manages context variables and provides LLM query capability.
    """
    
    def __init__(self, context: Union[str, Dict, List] = "", llm_query_fn: Optional[Callable] = None):
        """Initialize REPL with optional context and llm_query function."""
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
        logger.info(f"Context updated: type={type(context).__name__}, size={len(str(context))}")
    
    def execute(self, code: str) -> Dict[str, Any]:
        """
        Execute Python code in the REPL environment.
        
        Returns:
            Dict with 'success', 'output', 'error', and 'variables'
        """
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
            
            logger.debug(f"Code executed successfully. Output length: {len(output)}")
            
        except Exception as e:
            sys.stdout = old_stdout
            error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
            result['error'] = error_msg
            result['output'] = self.output_buffer.getvalue()
            
            logger.warning(f"Code execution failed: {error_msg}")
        
        finally:
            self.output_buffer = StringIO()
            sys.stdout = old_stdout
        
        return result
    
    def get_variable(self, name: str) -> Any:
        """Get a variable from the environment."""
        if name in self.locals:
            return self.locals[name]
        elif name in self.globals:
            return self.globals[name]
        return None
    
    def get_context_info(self) -> Dict[str, Any]:
        """Get comprehensive information about the current context."""
        context = self.globals.get('context', '')
        
        info = {
            'type': type(context).__name__,
        }
        
        if isinstance(context, str):
            info['total_chars'] = len(context)
            info['total_lines'] = context.count('\n') + 1
            info['size_kb'] = round(len(context) / 1024, 2)
        elif isinstance(context, dict):
            info['num_keys'] = len(context)
            info['keys_sample'] = list(context.keys())[:10]
            context_str = json.dumps(context)
            info['total_chars'] = len(context_str)
            info['size_kb'] = round(len(context_str) / 1024, 2)
        elif isinstance(context, list):
            info['num_items'] = len(context)
            if context:
                info['item_type'] = type(context[0]).__name__
            context_str = json.dumps(context)
            info['total_chars'] = len(context_str)
            info['size_kb'] = round(len(context_str) / 1024, 2)
        
        return info


class RLMMiddleware(AgentMiddleware):
    """
    Middleware that equips an agent with RLM capabilities:
    
    1. Persistent REPL environment with 'context' variable
    2. Tools for code execution and context management
    3. Sub-LLM query capability via llm_query() function
    4. Automatic offloading of large tool outputs
    5. System prompt injection for RLM guidance
    
    This middleware enhances agent capabilities without hijacking control.
    The agent decides when and how to use RLM tools.
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
            config: Configuration for RLM behavior.
            initial_context: Initial data to load into the RLM context variable.
        """
        super().__init__()
        self.model = model
        self.config = config or RLMConfig()
        self.current_depth = 0
        self._system_prompt_injected = False
        
        # Initialize persistent REPL environment
        self.env = REPLEnvironment(
            context=initial_context,
            llm_query_fn=self._llm_query_impl if self.config.enable_sub_calls else None
        )
        
        logger.info("RLM Middleware initialized")
        
    def _llm_query_impl(self, prompt: str) -> str:
        """
        Internal implementation of llm_query for recursive sub-calls.
        
        This is exposed to the REPL environment and can be called from
        code executed via rlm_execute_code.
        """
        if self.current_depth >= self.config.max_recursion_depth:
            return "ERROR: Maximum recursion depth reached. Cannot make more sub-LLM calls."
        
        self.current_depth += 1
        try:
            logger.debug(f"Sub-LLM query at depth {self.current_depth}: {prompt[:100]}...")
            messages = [HumanMessage(content=prompt)]
            response = self.model.invoke(messages)
            result = response.content
            logger.debug(f"Sub-LLM response length: {len(str(result))}")
        except Exception as e:
            result = f"ERROR in llm_query: {str(e)}"
            logger.error(f"Sub-LLM query failed: {str(e)}")
        finally:
            self.current_depth -= 1
            
        return str(result)

    @property
    def tools(self) -> List[BaseTool]:
        """
        Return the RLM tools provided to the agent.
        
        These tools give the agent control over the RLM environment.
        """
        return [
            self._create_load_context_tool(),
            self._create_repl_tool(),
            self._create_context_info_tool(),
            self._create_get_variable_tool(),
        ]

    @property
    def system_prompt(self) -> str:
        """
        Generate comprehensive RLM system prompt with current context info.
        
        This prompt educates the agent on how to use RLM capabilities.
        """
        context_info = self.env.get_context_info()
        
        # Build context info string
        if context_info.get('type') == 'dict':
            context_desc = f"Dictionary with {context_info.get('num_keys', 0)} keys"
            if 'keys_sample' in context_info:
                context_desc += f" (sample: {context_info['keys_sample'][:5]})"
        elif context_info.get('type') == 'list':
            context_desc = f"List with {context_info.get('num_items', 0)} items"
        elif context_info.get('type') == 'str':
            context_desc = f"String with {context_info.get('total_chars', 0):,} characters"
        else:
            context_desc = f"{context_info.get('type', 'Unknown')}"
        
        size_info = f"{context_info.get('size_kb', 0):.2f} KB" if 'size_kb' in context_info else "N/A"
        
        sub_call_instructions = ""
        if self.config.enable_sub_calls:
            sub_call_instructions = """
**llm_query(prompt: str) -> str**
   Available inside REPL code to query a sub-LLM for semantic analysis.
   Use for: understanding text, classification, extraction, summarization.
   Example in code:
   ```python
   chunk = context['device-1']['config']
   analysis = llm_query(f"Find security issues in this config:\\n{chunk}")
   print(analysis)
   ```
"""

        return f"""# RLM (Recursive Language Model) Capabilities

You have access to a **persistent Python REPL environment** for handling large datasets and contexts.

## Current Context
- **Type**: {context_desc}
- **Size**: {size_info}
- **Variable name**: `context`
- **Available modules**: json, re

{sub_call_instructions}

## Available Tools

### 1. rlm_execute_code
Execute Python code to inspect, filter, or process the 'context' variable.
- Code persists across calls - variables you create remain available
- Use to filter large datasets programmatically
- Call llm_query() inside code for semantic analysis of chunks
- Output is truncated if too long

**Example - Finding devices with issues:**
```python
# Filter devices with BGP problems
problem_devices = {{}}
for device_id, data in context.items():
    if 'bgp_neighbors' in data:
        down_neighbors = [n for n in data['bgp_neighbors'] if n['state'] != 'Established']
        if down_neighbors:
            problem_devices[device_id] = {{'device': data, 'down_neighbors': down_neighbors}}
print(f"Found {{len(problem_devices)}} devices with BGP issues")
```

**Example - Semantic analysis with llm_query:**
```python
# Analyze in chunks to avoid overwhelming context
results = []
devices_list = list(context.items())
chunk_size = 20

for i in range(0, len(devices_list), chunk_size):
    chunk = dict(devices_list[i:i+chunk_size])
    analysis = llm_query(f"Analyze these network devices for critical issues:\\n{{chunk}}")
    results.append(analysis)
    print(f"Processed chunk {{i//chunk_size + 1}}")

# Store results for later use
analysis_results = results
```

### 2. rlm_load_context
Load new data into the 'context' variable (replaces current content).
- Accepts JSON strings or plain text
- Useful when you fetch large data from other tools

### 3. rlm_context_info
Get current context metadata (type, size, structure).
- Use before processing to understand what you're working with

### 4. rlm_get_variable
Retrieve a variable you created in previous rlm_execute_code calls.
- Useful to get results from code execution without truncation

## Network Device Analysis Patterns

### Pattern 1: Filter then Analyze
```python
# Step 1: Filter programmatically (fast, cheap)
high_cpu = {{k: v for k, v in context.items() if v.get('cpu', 0) > 80}}

# Step 2: Analyze semantically (slower, uses sub-LLM)
if high_cpu:
    analysis = llm_query(f"Analyze why these devices have high CPU:\\n{{high_cpu}}")
```

### Pattern 2: Chunk Processing
```python
# For large device sets, process in chunks
chunk_size = 50
all_issues = []

for i in range(0, len(context), chunk_size):
    chunk = dict(list(context.items())[i:i+chunk_size])
    issues = llm_query(f"Find security issues in chunk {{i//chunk_size}}:\\n{{chunk}}")
    all_issues.append(issues)
```

### Pattern 3: Multi-level Analysis
```python
# Level 1: Quick filter with code
candidates = {{k: v for k, v in context.items() if 'config' in v}}

# Level 2: Deep analysis with llm_query
for device_id in list(candidates.keys())[:10]:  # Limit to avoid overload
    config = candidates[device_id]['config']
    assessment = llm_query(f"Security audit for {{device_id}}:\\n{{config}}")
    print(f"{{device_id}}: {{assessment[:100]}}...")
```

## Best Practices
1. **Always probe context first**: Use rlm_context_info or print samples
2. **Filter with code**: Use Python for syntactic filtering (regex, conditionals)
3. **Analyze with llm_query**: Use sub-LLM for semantic understanding
4. **Chunk large operations**: Process 10-50 items at a time
5. **Store intermediate results**: Save to variables for multi-step analysis
6. **Check output sizes**: Large outputs are automatically offloaded to context

## Important Notes
- Tool outputs >50KB are automatically loaded into 'context' variable
- Use rlm_execute_code to inspect them instead of reading directly
- Variables persist across your code executions in this conversation
- The agent has full autonomy - use RLM tools when appropriate for your task
"""

    def before_model(self, state, runtime):
        """
        Hook called before model invocation.
        
        Injects RLM system prompt on first call to educate the agent.
        """
        if not self._system_prompt_injected:
            messages = state.get("messages", [])
            
            # Check if system message already exists
            has_system = any(
                isinstance(m, SystemMessage) for m in messages
            )
            
            if not has_system:
                logger.info("Injecting RLM system prompt")
                self._system_prompt_injected = True
                return {
                    "messages": [SystemMessage(content=self.system_prompt)] + messages
                }
        
        return None

    def _create_load_context_tool(self) -> BaseTool:
        """Create tool for loading data into context."""
        def load_context_func(data: str) -> str:
            """
            Load data into the RLM 'context' variable.
            
            Args:
                data: JSON string or plain text to load
                
            Returns:
                Confirmation message with context info
            """
            # Attempt to parse as JSON for better structure
            try:
                parsed = json.loads(data)
                self.env.set_context(parsed)
                info = self.env.get_context_info()
                return f"✓ Context loaded as {info['type']}. Size: {info.get('size_kb', 'N/A')} KB"
            except json.JSONDecodeError:
                self.env.set_context(data)
                info = self.env.get_context_info()
                return f"✓ Context loaded as string. Size: {info.get('size_kb', 'N/A')} KB"

        return StructuredTool.from_function(
            func=load_context_func,
            name="rlm_load_context",
            description=(
                "Load text or JSON data into the global 'context' variable for inspection. "
                "Use this when you receive large data from other tools that you want to analyze with code."
            )
        )

    def _create_repl_tool(self) -> BaseTool:
        """Create tool for executing code in REPL."""
        def repl_func(code: str) -> str:
            """
            Execute Python code in the RLM environment.
            
            Args:
                code: Python code to execute. Can use 'context', 'json', 're', 'llm_query'.
                
            Returns:
                Execution output and variables created
            """
            result = self.env.execute(code)
            
            if result['success']:
                output = result['output']
                if len(output) > self.config.truncate_output_chars:
                    output = output[:self.config.truncate_output_chars] + \
                            f"\n... (output truncated, {len(result['output'])} total chars)"
                
                # Format response
                response_parts = []
                if output.strip():
                    response_parts.append(f"Output:\n{output}")
                
                if result['variables']:
                    var_list = ", ".join(result['variables'].keys())
                    response_parts.append(f"Variables created/updated: {var_list}")
                    # Show variable previews
                    for var_name, var_preview in list(result['variables'].items())[:5]:
                        response_parts.append(f"  {var_name} = {var_preview}")
                
                return "\n".join(response_parts) if response_parts else "✓ Code executed (no output)"
            else:
                return f"✗ Error:\n{result['error']}"
        
        return StructuredTool.from_function(
            func=repl_func,
            name="rlm_execute_code",
            description=(
                "Execute Python code to inspect 'context' or process data. "
                "Variables persist across calls. You can call llm_query(prompt) inside the code "
                "to query a sub-LLM for semantic analysis of text chunks."
            )
        )
    
    def _create_context_info_tool(self) -> BaseTool:
        """Create tool for getting context information."""
        def info_func() -> str:
            """
            Get information about the current data in 'context'.
            
            Returns:
                JSON string with context metadata
            """
            info = self.env.get_context_info()
            return json.dumps(info, indent=2)
            
        return StructuredTool.from_function(
            func=info_func,
            name="rlm_context_info",
            description=(
                "Get information about the current data in 'context' variable "
                "(type, size, structure). Use this before processing to understand the data."
            )
        )
    
    def _create_get_variable_tool(self) -> BaseTool:
        """Create tool for retrieving variables from REPL."""
        def get_var_func(variable_name: str) -> str:
            """
            Retrieve a variable created in rlm_execute_code.
            
            Args:
                variable_name: Name of the variable to retrieve
                
            Returns:
                String representation of the variable value
            """
            value = self.env.get_variable(variable_name)
            if value is None:
                available = list(self.env.locals.keys())
                return f"✗ Variable '{variable_name}' not found. Available: {available}"
            
            # Convert to JSON if possible for better structure
            try:
                if isinstance(value, (dict, list)):
                    return json.dumps(value, indent=2)
            except:
                pass
            
            return str(value)
            
        return StructuredTool.from_function(
            func=get_var_func,
            name="rlm_get_variable",
            description=(
                "Retrieve a variable you created in previous rlm_execute_code calls. "
                "Useful to get full results without truncation."
            )
        )

    def wrap_model_call(self, request, next_handler):
        """
        Intercept model calls to handle large tool outputs transparently.
        
        This middleware automatically offloads large tool outputs to the RLM context.
        """
        # Extract messages from request
        # request is likely a dict or object with 'messages'
        messages = None
        if isinstance(request, dict):
            messages = request.get('messages')
        elif hasattr(request, 'messages'):
            messages = request.messages
            
        if messages and isinstance(messages, list):
            modified = False
            
            # Find and handle large ToolMessages
            for i, msg in enumerate(messages):
                if isinstance(msg, ToolMessage) and isinstance(msg.content, str):
                    content_size = len(msg.content)
                    
                    if content_size > self.config.large_output_threshold:
                        logger.info(
                            f"Large tool output detected ({content_size} chars) "
                            f"from tool '{getattr(msg, 'name', 'unknown')}'. "
                            "Offloading to RLM context."
                        )
                        
                        # Offload to RLM context
                        self.env.set_context(msg.content)
                        
                        # Create informative summary
                        preview = msg.content[:self.config.context_preview_chars].replace('\n', ' ')
                        tool_name = getattr(msg, 'name', 'unknown')
                        
                        summary = (
                            f"📦 LARGE OUTPUT OFFLOADED TO RLM CONTEXT\n"
                            f"Tool: {tool_name}\n"
                            f"Size: {content_size:,} characters ({content_size/1024:.2f} KB)\n"
                            f"Status: Full output loaded into 'context' variable\n\n"
                            f"Preview (first {self.config.context_preview_chars} chars):\n"
                            f"{preview}...\n\n"
                            f"💡 Use 'rlm_execute_code' to inspect and filter the 'context' variable.\n"
                            f"   Example: context[:1000] to see first 1000 chars\n"
                            f"   Example: len(context) to check size\n"
                            f"   Use 'rlm_context_info' to see structure info."
                        )
                        
                        # Create new message with summary
                        try:
                            new_kwargs = {
                                "content": summary,
                            }
                            if hasattr(msg, 'tool_call_id'):
                                new_kwargs['tool_call_id'] = msg.tool_call_id
                            if hasattr(msg, 'name'):
                                new_kwargs['name'] = msg.name
                            if hasattr(msg, 'additional_kwargs'):
                                new_kwargs['additional_kwargs'] = msg.additional_kwargs
                                
                            messages[i] = ToolMessage(**new_kwargs)
                            modified = True
                            
                        except Exception as e:
                            logger.error(f"Failed to create summary message: {e}")
                            # Fallback: try direct mutation
                            try:
                                msg.content = summary
                                modified = True
                            except Exception as e2:
                                logger.error(f"Failed to mutate message: {e2}")
            
            # If we modified messages, we need to update the request
            if modified:
                if isinstance(request, dict):
                    request['messages'] = messages
                elif hasattr(request, 'messages'):
                    # Careful if mutable or not
                    try:
                        request.messages = messages
                    except:
                        pass
        
        return next_handler(request)


class NetworkDeviceRLMMiddleware(RLMMiddleware):
    """
    Specialized RLM middleware optimized for network device contexts.
    
    Pre-configured with:
    - Lower threshold for large outputs (network data tends to be bulky)
    - Network-specific examples in system prompt
    - Extended iteration limit for complex network analysis
    """
    
    def __init__(
        self,
        model: BaseChatModel,
        config: Optional[RLMConfig] = None,
        initial_context: Union[str, Dict, List, Any] = ""
    ):
        """
        Initialize Network Device RLM Middleware.
        
        Args:
            model: The LLM to use for recursive sub-calls
            config: Optional configuration (uses network-optimized defaults)
            initial_context: Initial network data to load
        """
        # Network-optimized defaults
        if config is None:
            config = RLMConfig(
                max_recursion_depth=1,
                max_iterations=50,  # Network analysis can be complex
                large_output_threshold=30000,  # Lower threshold (30KB)
                truncate_output_chars=5000,
                context_preview_chars=500,
            )
        
        super().__init__(model=model, config=config, initial_context=initial_context)
        logger.info("Network Device RLM Middleware initialized")
    
    @property
    def system_prompt(self) -> str:
        """
        Enhanced system prompt with network-specific guidance.
        """
        base_prompt = super().system_prompt
        
        network_specific = """

## Network Device Analysis Quick Reference

### Common Tasks

**1. Find Devices with Configuration Issues**
```python
# Search configs for security issues
import re
issues = {}
for device_id, data in context.items():
    config = data.get('config', '')
    if re.search(r'snmp-server community public', config, re.IGNORECASE):
        issues[device_id] = 'Default SNMP community'
    if 'telnet' in config.lower():
        issues[device_id] = issues.get(device_id, '') + ' | Telnet enabled'
print(f"Found {len(issues)} devices with issues")
```

**2. Analyze Operational Status**
```python
# Find devices with critical operational issues
critical = {}
for device_id, data in context.items():
    facts = data.get('facts', {})
    
    # Check CPU/Memory
    if facts.get('cpu', 0) > 80 or facts.get('memory', 0) > 85:
        critical[device_id] = 'Resource exhaustion'
    
    # Check BGP
    if 'bgp_neighbors' in facts:
        down = [n for n in facts['bgp_neighbors'] if n.get('state') != 'Established']
        if down:
            critical[device_id] = f'BGP: {len(down)} sessions down'
            
print(f"Critical devices: {len(critical)}")
```

**3. Cross-reference Config and Status**
```python
# Find misconfigurations causing operational issues
misconfig = {}
for device_id, data in context.items():
    config = data.get('config', '')
    facts = data.get('facts', {})
    
    # BGP configured but all sessions down?
    if 'router bgp' in config.lower():
        neighbors = facts.get('bgp_neighbors', [])
        if neighbors and all(n.get('state') != 'Established' for n in neighbors):
            misconfig[device_id] = 'BGP configured but all sessions down'
            
print(f"Possible misconfigurations: {len(misconfig)}")
```

**4. Aggregate Analysis Across Device Types**
```python
# Group by device type and analyze patterns
from collections import defaultdict
by_type = defaultdict(list)

for device_id, data in context.items():
    device_type = data.get('facts', {}).get('model', 'unknown')
    by_type[device_type].append(device_id)

# Analyze each type
for dev_type, devices in by_type.items():
    print(f"\\n{dev_type}: {len(devices)} devices")
    # Could use llm_query here for deeper analysis per type
```

**5. Root Cause Analysis with llm_query**
```python
# Step 1: Filter to problem devices
problems = {k: v for k, v in context.items() if v.get('has_issue')}

# Step 2: Chunk and analyze with sub-LLM
chunk_size = 10
analyses = []

for i in range(0, len(problems), chunk_size):
    chunk = dict(list(problems.items())[i:i+chunk_size])
    
    # Use llm_query for semantic analysis
    analysis = llm_query(
        f"Analyze these network devices for root cause of issues. "
        f"Look for common patterns in configs and operational status:\\n"
        f"{json.dumps(chunk, indent=2)}"
    )
    analyses.append(analysis)
    print(f"Analyzed chunk {i//chunk_size + 1}/{(len(problems)-1)//chunk_size + 1}")

# Step 3: Synthesize findings
root_cause = llm_query(
    f"Based on these analyses, identify the root cause:\\n" + 
    "\\n---\\n".join(analyses)
)
print(f"\\nRoot Cause Analysis:\\n{root_cause}")
```

### Performance Tips for Large Networks (1000+ devices)

1. **Progressive filtering**: Use code to narrow down before llm_query
2. **Sampling**: Analyze representative samples, not all devices
3. **Caching**: Store intermediate results in variables
4. **Chunking**: Process 10-50 devices per llm_query call
5. **Parallel patterns**: Group similar devices and analyze once

---
"""
        
        return base_prompt + network_specific
