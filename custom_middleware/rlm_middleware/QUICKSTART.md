# Quick Start Guide: RLM Middleware for Deep Agents

## Installation

```bash
pip install langchain langchain-openai deepagents
```

## Basic Example with Deep Agents

```python
from rlm_middleware import RLMMiddleware, RLMConfig
from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

# Initialize Middleware
# - Handles RLM tools (repl, load_context)
# - Injects RLM system prompt
middleware = RLMMiddleware(
    model=ChatOpenAI(model="gpt-3.5-turbo", temperature=0), # Sub-LLM
    config=RLMConfig(max_iterations=10)
)

# Create Agent
agent = create_deep_agent(
    model=ChatOpenAI(model="gpt-4", temperature=0),
    middleware=[middleware]
)

# Create context - 100 devices with facts
device_data = {
    f'router-{i}': {
        'hostname': f'rtr-{i}',
        'bgp_state': 'Established' if i % 10 != 0 else 'Idle'
    }
    for i in range(100)
}

# Run Agent
# You can load context dynamically using the provided tool, or pass it in init
# Here we let the agent know about the context via tool or prompt
query = f"""
I have mapped the device data to this JSON: {str(device_data)[:100]}... (large data).
Please load this data into your RLM context and find how many routers have 'Idle' BGP state.
"""

# Alternatively, use rlm_load_context tool directly if interacting programmatically
# Or initialize middleware with initial_context variable
middleware.env.set_context(device_data)

response = agent.invoke({"messages": [HumanMessage(content="How many routers have BGP state Idle?")]})
print(response['messages'][-1].content)
```

## How It Works

1. **RLMMiddleware** adds specialized tools to your agent:
   - `rlm_read_context_info`: Check data size/type.
   - `rlm_execute_code`: Run Python code to filter data.
   - `rlm_load_context`: Load data into the environment.

2. The Agent uses these tools to "think" about large data without loading it all into its context window.

3. The Agent can make **recursive calls** (if enabled) via `llm_query` within the Python code to process chunks of data semantically.
