# Enhanced Debugging - Agent Hang Issue

## Issue Summary
The app hangs at "Adding user message to history" and never reaches the agent.astream() call.

## Enhanced Logging Added

I've added very detailed logging at the critical section where it's hanging:

### In agent_service.py:
```python
logger.debug("Adding user message to history")
logger.debug("About to add stream log...")
logger.debug("Stream log added successfully")
logger.info("=== ENTERING TRY BLOCK ===")
logger.info(f"Agent object: {self.agent}")
logger.info(f"Agent type: {type(self.agent)}")
logger.info("About to call agent.astream()...")
logger.info(f"Agent input prepared: {agent_input}")
logger.info("=== CALLING agent.astream() NOW ===")
# async for loop starts
logger.info(f"=== INSIDE ASYNC FOR LOOP - Got first chunk! ===")
```

### In net_deepagent.py (create_network_agent):
```python
logger.info("=== create_network_agent() called ===")
logger.info("Creating MCP client...")
logger.info("MCP client created successfully")
logger.info("Getting tools from MCP client...")
logger.info(f"Got {len(tools)} tools from MCP")
logger.info("Creating deep agent with create_deep_agent()...")
logger.info(f"Deep agent created successfully! Type: {type(net_deep_agent)}")
logger.info("=== create_network_agent() complete ===")
```

## How to Run

```bash
cd /home/toffe/workspace/agentic
conda activate test_langchain_env
streamlit run ui/app.py 2>&1 | tee debug.log
```

## What to Look For

### Scenario 1: Hangs Before "ENTERING TRY BLOCK"
**Last log seen:**
```
DEBUG - Adding user message to history
DEBUG - About to add stream log...
(nothing after)
```

**Problem:** `session_manager.add_stream_log()` is hanging
**Solution:** Check session_manager.py for blocking operations

---

### Scenario 2: Hangs After "ENTERING TRY BLOCK" but Before "CALLING agent.astream()"
**Last log seen:**
```
INFO - === ENTERING TRY BLOCK ===
INFO - Agent object: <something>
INFO - Agent type: <type>
(nothing after)
```

**Problem:** Something wrong with agent object or input preparation
**Solution:** Check the agent object value in logs

---

### Scenario 3: Hangs At "CALLING agent.astream() NOW"
**Last log seen:**
```
INFO - === CALLING agent.astream() NOW ===
(nothing after - NEVER reaches "INSIDE ASYNC FOR LOOP")
```

**Problem:** `agent.astream()` call itself is blocking/hanging
**Causes:**
1. **MCP server not responding** - Most likely!
2. **Agent waiting for model API response**
3. **DeepAgents library has an internal hang**

**Debug steps:**
```bash
# Test MCP server
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tools/list", "id": 1}'

# Should return list of tools
```

---

### Scenario 4: Never Gets Past Agent Initialization
**Last log seen during startup:**
```
INFO - Creating network agent...
INFO - === create_network_agent() called ===
INFO - Creating MCP client...
(hangs here)
```

**Problem:** MCP client creation is hanging
**Solution:** MCP server not running or not accessible

```bash
# Check if MCP server is running
netstat -tlnp | grep 8000

# Try to access it
curl http://localhost:8000/mcp
```

---

## Expected Good Logs

### Startup:
```
INFO - === create_network_agent() called ===
INFO - Creating MCP client...
INFO - MCP client created successfully
INFO - Getting tools from MCP client...
INFO - Got 10 tools from MCP
INFO - Creating deep agent with create_deep_agent()...
INFO - Deep agent created successfully! Type: <class 'langgraph...'>
INFO - === create_network_agent() complete ===
INFO - Agent initialized successfully!
```

### Message Processing:
```
INFO - Send button clicked. User input: test message...
DEBUG - Adding user message to history
DEBUG - About to add stream log...
DEBUG - Stream log added successfully
INFO - === ENTERING TRY BLOCK ===
INFO - Agent object: <Pregel object>
INFO - Agent type: <class 'langgraph.pregel.Pregel'>
INFO - About to call agent.astream()...
INFO - Agent input prepared: {'messages': 'test message'}
INFO - === CALLING agent.astream() NOW ===
INFO - === INSIDE ASYNC FOR LOOP - Got first chunk! ===
DEBUG - Received chunk #1: <class 'dict'>
```

---

## Quick Diagnosis Checklist

Run the app and check logs:

1. **Does it reach "=== ENTERING TRY BLOCK ==="?**
   - [ ] No → session_manager issue
   - [ ] Yes → Continue

2. **Does it reach "=== CALLING agent.astream() NOW ==="?**
   - [ ] No → Agent object is None or malformed
   - [ ] Yes → Continue

3. **Does it reach "=== INSIDE ASYNC FOR LOOP - Got first chunk! ==="?**
   - [ ] No → agent.astream() is hanging (MCP/API issue)
   - [ ] Yes → Streaming works! Different issue

---

## Most Likely Issue: MCP Server

If logs show:
```
INFO - === CALLING agent.astream() NOW ===
(hangs forever, never reaches INSIDE ASYNC FOR LOOP)
```

**The agent.astream() is waiting for MCP server to respond.**

### Fix:
1. **Check MCP server status:**
   ```bash
   curl http://localhost:8000/mcp
   ```

2. **Restart MCP server** if not running

3. **Check MCP server logs** for errors

4. **Test with a simple MCP call:**
   ```bash
   curl -X POST http://localhost:8000/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc": "2.0", "method": "tools/list", "id": 1}'
   ```

---

## Alternative: Test Without MCP

If MCP is the issue, you can temporarily modify net_deepagent.py to skip MCP:

```python
# In create_network_agent(), replace:
tools = await client.get_tools()

# With:
tools = []  # Empty tools list for testing
```

This will let you test if the agent works without MCP tools.

---

## Next Steps

1. Run the app with enhanced logging
2. Find the **last log message** before it hangs
3. Match it to one of the scenarios above
4. Follow the debug steps for that scenario
5. Share the logs showing the exact hang point

The logs will now show us EXACTLY where it's stopping!
