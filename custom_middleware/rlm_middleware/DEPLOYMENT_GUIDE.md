# RLM Middleware - Updated Deployment Guide

## ⚡ IMPORTANT UPDATE

The test scripts now use the **correct DeepAgents API**: `create_deep_agent` instead of the deprecated `create_react_agent`.

## 🚀 Quick Start (Updated)

### Installation

```bash
pip install deepagents langchain-openai
```

### Minimal Example

```python
from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI
from rlm_middleware_final import NetworkDeviceRLMMiddleware

# 1. Create RLM middleware with your data
devices = {...}  # Your device data
sub_model = ChatOpenAI(model="gpt-3.5-turbo")

rlm = NetworkDeviceRLMMiddleware(
    model=sub_model,
    initial_context=devices  # Load all devices
)

# 2. Create deep agent
agent = create_deep_agent(
    model="gpt-4-turbo-preview",
    tools=rlm.tools,
    middleware=[rlm],
    system_prompt="You are a network analyst."
)

# 3. Run
result = agent.invoke({
    "messages": [{"role": "user", "content": "Find BGP issues"}]
})

print(result["messages"][-1].content)
```

## 📦 Updated Files

### Core Files
- **rlm_middleware_final.py** - Production middleware (no changes)
- **test_network_scenario.py** - ✅ UPDATED to use create_deep_agent
- **simple_example.py** - ✅ NEW minimal example
- **UPDATED_DEPLOYMENT_GUIDE.md** - This file

## 🔄 Key API Changes

### OLD (Deprecated)
```python
from langchain.agents import create_react_agent, AgentExecutor

agent = create_react_agent(llm=llm, tools=tools, prompt=prompt)
executor = AgentExecutor(agent=agent, tools=tools)
result = executor.invoke({"input": query})
```

### NEW (Current)
```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    model="gpt-4",
    tools=tools,
    middleware=[rlm]
)
result = agent.invoke({"messages": [{"role": "user", "content": query}]})
```

## 🎯 create_deep_agent Parameters

```python
agent = create_deep_agent(
    model="gpt-4-turbo-preview",        # LLM to use (can also pass ChatModel instance)
    tools=[...],                         # List of tools
    middleware=[rlm],                    # List of middleware
    system_prompt="...",                 # Custom instructions
    subagents=[...],                     # Optional sub-agents
    backend=FilesystemBackend(...),      # Optional storage backend
)
```

## 📊 Usage with RLM

### Pattern 1: Network Device Analysis

```python
from deepagents import create_deep_agent
from rlm_middleware_final import NetworkDeviceRLMMiddleware

# Load device data into RLM
rlm = NetworkDeviceRLMMiddleware(
    model=ChatOpenAI("gpt-3.5-turbo"),
    initial_context=device_facts
)

# Create agent
agent = create_deep_agent(
    model="gpt-4",
    tools=rlm.tools,
    middleware=[rlm],
    system_prompt="Network analyst. Use RLM tools for large datasets."
)

# Query
result = agent.invoke({
    "messages": [{
        "role": "user",
        "content": "Find security issues in configs"
    }]
})
```

### Pattern 2: Combining with Other Middleware

```python
from deepagents import create_deep_agent
from langchain.agents.middleware import TodoListMiddleware

agent = create_deep_agent(
    model="gpt-4",
    tools=rlm.tools,
    middleware=[
        TodoListMiddleware(),  # Built-in planning
        rlm,                   # Your RLM middleware
    ]
)
```

### Pattern 3: With Custom Tools

```python
from langchain_core.tools import tool

@tool
def get_device_status(device_id: str) -> str:
    """Get real-time device status."""
    return query_device(device_id)

agent = create_deep_agent(
    model="gpt-4",
    tools=[get_device_status] + rlm.tools,
    middleware=[rlm]
)
```

## 🧪 Testing

### Run Simple Example

```bash
export OPENAI_API_KEY='your-key'
python simple_example.py
```

### Run Full Network Scenario

```bash
python test_network_scenario.py
# Choose option 'y' to run full test
```

## 🎓 DeepAgents Built-in Features

When you use `create_deep_agent`, you automatically get:

### Built-in Tools (Free)
- `write_todos` / `read_todos` - Task planning
- `ls`, `read_file`, `write_file`, `edit_file` - File system
- `task` - Spawn sub-agents

### Built-in Middleware (Free)
- `TodoListMiddleware` - Planning
- `FilesystemMiddleware` - Context offloading (>20K tokens auto-saved to files)
- `SubAgentMiddleware` - Delegation
- `SummarizationMiddleware` - Auto-summarize at 170K tokens

### Your RLM Adds
- `rlm_execute_code` - Python REPL
- `rlm_load_context` - Load data
- `rlm_context_info` - Metadata
- `rlm_get_variable` - Retrieve results
- Automatic large output offloading via `wrap_model_call`

## 🔍 Debugging

### Enable Verbose Mode

DeepAgents agents return LangGraph graphs, so you can use standard LangGraph debugging:

```python
# Stream events
for chunk in agent.stream({"messages": [...]}, stream_mode="values"):
    print(chunk["messages"][-1])

# Print full state
result = agent.invoke({"messages": [...]})
print(result)  # See all messages, state, etc.
```

### Check RLM State

```python
# After agent runs
print(rlm.env.get_context_info())
print(rlm.env.locals.keys())  # Variables created
```

## 📈 Performance

For 1000 devices (~10MB):

| Metric | Value |
|--------|-------|
| Data load | <1s |
| Code execution | 1-2s each |
| Sub-LLM query | 3-5s each |
| Total time | 2-5 min |
| Cost (GPT-3.5 sub) | $0.50-$2 |

## 💡 Best Practices

### 1. Load Data Upfront

```python
# ✅ Good - load at initialization
rlm = NetworkDeviceRLMMiddleware(
    model=sub_model,
    initial_context=all_devices
)

# ❌ Bad - let agent load via tool (slower)
```

### 2. Use Sub-Model for Cost Savings

```python
# Main agent: GPT-4 (smart planning)
# Sub-LLM queries: GPT-3.5 (cheap semantic analysis)
rlm = NetworkDeviceRLMMiddleware(
    model=ChatOpenAI("gpt-3.5-turbo"),  # Used for llm_query()
)

agent = create_deep_agent(
    model="gpt-4",  # Used for main reasoning
    middleware=[rlm]
)
```

### 3. Guide the Agent

```python
system_prompt = """
You are a network analyst.

IMPORTANT: Device data is in RLM 'context' variable.
- Use rlm_execute_code to filter with Python (fast)
- Use llm_query() inside code for semantic analysis (slow)
- Process in chunks of 20-50 devices
"""
```

## 🚨 Common Issues

### Issue: "create_react_agent not found"

**Solution**: Update imports
```python
# OLD
from langchain.agents import create_react_agent

# NEW
from deepagents import create_deep_agent
```

### Issue: "Agent doesn't use RLM tools"

**Solution**: Check middleware injection
```python
agent = create_deep_agent(
    tools=rlm.tools,      # ✅ Include tools
    middleware=[rlm],     # ✅ Include middleware
)
```

### Issue: "Context not loaded"

**Solution**: Load at initialization
```python
rlm = NetworkDeviceRLMMiddleware(
    model=sub_model,
    initial_context=devices  # ✅ Load here
)
```

## 📚 Resources

- **DeepAgents Docs**: https://docs.langchain.com/oss/python/deepagents/
- **GitHub Examples**: https://github.com/langchain-ai/deepagents-quickstarts
- **API Reference**: https://reference.langchain.com/python/deepagents/

## ✅ Migration Checklist

- [ ] Install deepagents: `pip install deepagents`
- [ ] Replace `create_react_agent` with `create_deep_agent`
- [ ] Update invoke syntax: `{"messages": [...]}`
- [ ] Test with simple_example.py
- [ ] Run full scenario test
- [ ] Update your production code

---

**Ready to test! Run `python simple_example.py` to see it in action.** 🚀