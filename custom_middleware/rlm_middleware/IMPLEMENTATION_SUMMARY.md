# RLM Middleware for Deep Agents - Implementation Summary

## What We Built

A **Recursive Language Model (RLM) Middleware** compatible with the `deepagents` framework / LangChain `AgentMiddleware` interface.

This implementation allows an agent to handle arbitrarily long contexts by treating them as external environment data, accessible via a Python REPL and recursive sub-calls.

## Key Files

1. **rlm_middleware.py** - Main implementation
   - `RLMMiddleware` - The middleware class adhering to AgentMiddleware interface.
   - `REPLEnvironment` - Sandboxed Python execution environment.
   - `RLMConfig` - Configuration dataclass.

2. **test_rlm_basic.py** - Tests
   - Validates middleware tools (`rlm_execute_code`, etc).
   - Validates REPL environment.

3. **example_network_analysis.py** - Usage Example
   - Demonstrates how to integrate `RLMMiddleware` into a Deep Agent for network analysis tasks.

## Architecture

### RLMMiddleware

The middleware injects RLM capabilities into any Deep Agent:

- **System Prompt Injection**: Adds instructions on how to use the REPL and process large data.
- **Tools**:
  - `rlm_load_context(data)`: Loads data into the persistent environment.
  - `rlm_execute_code(code)`: Executes Python code to inspect, filter, or aggregate the data.
  - `rlm_context_info()`: Checks the size/structure of the current data.
- **Recursion**:
  - Inside `rlm_execute_code`, the model can call `llm_query(prompt)` to trigger a recursive call to a sub-model (e.g. for semantic summarization of a chunk).

### Usage Pattern

1. **Instantiation**:
   ```python
   middleware = RLMMiddleware(model=sub_llm, config=RLMConfig(...))
   ```
2. **Integration**:
   ```python
   agent = create_deep_agent(..., middleware=[middleware])
   ```
3. **Execution**:
   The agent receives a query. It discovers it has a large dataset (e.g. loaded via tool). It uses `rlm_execute_code` to filter the dataset using Python, then potentially uses `llm_query` to analyze the filtered results, before returning a final answer.

## Performance & Benefits

- **Scalability**: Can process contexts much larger than the LLM window by accessing them as a variable in REPL.
- **Cost**: Filters data programmatically (free) before sending to LLM (paid).
- **Flexibility**: Works with any agent logic (ReAct, Plan-and-Solve) provided by the `deepagents` framework.

## Next Steps

- Integrate with specific vector stores or external APIs via custom `load_context` adapters.
- Extend `REPLEnvironment` with more specialized libraries (pandas, networkx).
