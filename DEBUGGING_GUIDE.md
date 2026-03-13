# Network AI Assistant - Debugging Guide

## Logging Enabled ✅

Comprehensive logging has been added to all modules to help debug issues.

---

## How to Run with Logging

### 1. **Start MCP Server First**
```bash
# Make sure your MCP server is running on http://localhost:8000/mcp
# If not, start it before running the UI
```

### 2. **Run Streamlit with Console Logging**
```bash
# Activate environment
conda activate test_langchain_env

# Navigate to project directory
cd /home/<user>/workspace/agentic

# Run Streamlit (logs will appear in console)
streamlit run ui/app.py
```

### 3. **Alternative: Run with Log File**
```bash
# Run and save logs to file
streamlit run ui/app.py 2>&1 | tee app.log
```

---

## What to Look for in Logs

### On Startup

You should see:
```
==================================================
Streamlit UI Starting
==================================================
INFO - Getting AgentService singleton
INFO - Initializing AgentService singleton
INFO - AgentService initialized successfully
INFO - Agent service retrieved: True
INFO - First run - initializing agent
INFO - Calling agent_service.initialize()...
INFO - Starting agent initialization
DEBUG - MCP URL: http://localhost:8000/mcp
DEBUG - Main model: gpt-5-mini
INFO - Creating network agent...
```

**If you see errors here:**
- Check if MCP server is running
- Verify network connectivity to MCP server
- Check API keys are set in `~/.net-deepagent/creds.json`

### When Clicking Send Button

You should see:
```
INFO - Send button clicked. User input: <your message>...
INFO - Session ID: <uuid>
INFO - Selected model: gpt-5-mini
INFO - Creating response placeholder
INFO - Entered stream_agent_response async function
INFO - About to call agent_service.stream_response()
INFO - Stream response started for session <uuid>
DEBUG - Message: <your message>...
INFO - Starting agent.astream()...
DEBUG - Calling agent.astream with message: <your message>...
```

**If it hangs at "agent.astream()":**
- The agent is waiting for a response from the backend
- Check if net_deepagent is properly initialized
- Look for errors in the MCP connection

### During Streaming

You should see:
```
DEBUG - Received chunk #1: <class 'dict'>
DEBUG - Model response chunk: ...
INFO - UI received chunk #1, type: model
DEBUG - Updated UI with model content: ...
```

**If no chunks are received:**
- Agent is not producing output
- Check MCP tools are responding
- Verify models are accessible

---

## Common Issues and Solutions

### Issue 1: "Agent is thinking forever"

**Symptoms:**
- Send button clicked
- Shows "Agent is thinking..."
- Never completes

**Check logs for:**
```
INFO - Starting agent.astream()...
```

If it stops here, the agent.astream() is hanging.

**Possible causes:**
1. **MCP server not responding**
   - Solution: Check `http://localhost:8000/mcp` is accessible
   - Test with: `curl http://localhost:8000/mcp`

2. **Model API not responding**
   - Solution: Verify API keys in `~/.net-deepagent/creds.json`
   - Check network access to OpenAI/Anthropic/Google APIs

3. **Agent waiting for tool response**
   - Solution: Check MCP tools are working
   - Look for tool call logs

### Issue 2: "AgentService not initialized"

**Symptoms:**
- Error on startup or first message

**Check logs for:**
```
ERROR - Failed to create network agent: <error>
```

**Solutions:**
- Verify `~/.net-deepagent/creds.json` has valid API keys
- Check MCP server is running
- Ensure all dependencies are installed

### Issue 3: No logs appearing

**Symptoms:**
- Console shows no DEBUG/INFO logs

**Solutions:**
```python
# In ui/app.py, ensure logging level is DEBUG:
logging.basicConfig(level=logging.DEBUG, ...)
```

### Issue 4: Import errors

**Symptoms:**
- ModuleNotFoundError on startup

**Solutions:**
```bash
# Reinstall dependencies
pip install -r requirements.txt

# Verify environment
conda activate test_langchain_env
python -c "import langchain_core; print('OK')"
```

---

## Log Levels Explained

- **DEBUG**: Detailed information, typically of interest only when diagnosing problems
- **INFO**: Confirmation that things are working as expected
- **WARNING**: An indication that something unexpected happened
- **ERROR**: A serious problem, the software has not been able to perform some function

---

## Debugging Steps

### Step 1: Check Initialization
1. Run app: `streamlit run ui/app.py`
2. Look for: `INFO - Agent initialized successfully!`
3. If error, check MCP server and API keys in `~/.net-deepagent/creds.json`

### Step 2: Test Message Sending
1. Type a message and click Send
2. Look for: `INFO - Send button clicked`
3. Check: `INFO - About to call agent_service.stream_response()`

### Step 3: Monitor Streaming
1. Look for: `DEBUG - Received chunk #<number>`
2. Check: `INFO - UI received chunk #<number>`
3. Verify chunks are arriving

### Step 4: Check Completion
1. Look for: `INFO - Streaming complete. Total chunks: <number>`
2. Check: `INFO - Status updated to complete`
3. Verify: `INFO - About to rerun Streamlit`

---

## Advanced Debugging

### Enable Even More Verbose Logging

Edit `services/agent_service.py` and `ui/app.py`:

```python
# Change logging level to DEBUG everywhere
logging.basicConfig(level=logging.DEBUG, ...)

# Add more log statements
logger.debug(f"Variable value: {some_var}")
```

### Check Individual Components

#### Test AgentService directly:
```python
import asyncio
from services.agent_service import AgentService

async def test():
    service = AgentService()
    await service.initialize()
    print("Service initialized!")

    async for chunk in service.stream_response("test message", "test-session"):
        print(f"Chunk: {chunk}")

asyncio.run(test())
```

#### Test net_deepagent directly:
```bash
# Run standalone mode
python net_deepagent.py
```

---

## Collecting Logs for Support

If you need to share logs:

```bash
# Run and save complete log
streamlit run ui/app.py 2>&1 | tee full_debug.log

# Share full_debug.log
```

---

## Module-Specific Logging

### agent_service.py
- Logs all stream chunks
- Logs tool calls
- Logs errors with traceback

### ui/app.py
- Logs button clicks
- Logs async function entry/exit
- Logs chunk reception

### net_deepagent.py
- Logs agent creation
- Logs MCP connection
- Logs model initialization

---

## Quick Checklist

Before running:
- [ ] MCP server running at http://localhost:8000/mcp
- [ ] API keys set in `~/.net-deepagent/creds.json`
- [ ] Conda environment activated
- [ ] Dependencies installed

When running:
- [ ] Watch console for logs
- [ ] Check for "Agent initialized successfully"
- [ ] Verify "Send button clicked" appears
- [ ] Monitor chunk reception
- [ ] Check for errors in red

---

## Example: Good Startup Logs

```
2026-01-04 10:30:01 - __main__ - INFO - ==================================================
2026-01-04 10:30:01 - __main__ - INFO - Streamlit UI Starting
2026-01-04 10:30:01 - __main__ - INFO - ==================================================
2026-01-04 10:30:02 - __main__ - INFO - Getting AgentService singleton
2026-01-04 10:30:02 - services.agent_service - INFO - Initializing AgentService singleton
2026-01-04 10:30:02 - services.agent_service - INFO - AgentService initialized successfully
2026-01-04 10:30:02 - __main__ - INFO - Agent service retrieved: True
2026-01-04 10:30:02 - __main__ - INFO - First run - initializing agent
2026-01-04 10:30:02 - __main__ - INFO - Calling agent_service.initialize()...
2026-01-04 10:30:02 - services.agent_service - INFO - Starting agent initialization
2026-01-04 10:30:02 - services.agent_service - DEBUG - MCP URL: http://localhost:8000/mcp
2026-01-04 10:30:02 - services.agent_service - DEBUG - Main model: gpt-5-mini
2026-01-04 10:30:02 - services.agent_service - INFO - Creating network agent...
2026-01-04 10:30:05 - services.agent_service - INFO - Network agent created successfully
2026-01-04 10:30:05 - services.agent_service - DEBUG - Setting up clarification callback
2026-01-04 10:30:05 - services.agent_service - INFO - Agent initialization complete
2026-01-04 10:30:05 - __main__ - INFO - Agent initialized successfully!
```

## Example: Good Message Processing Logs

```
2026-01-04 10:31:00 - __main__ - INFO - Send button clicked. User input: What is the network issue?...
2026-01-04 10:31:00 - __main__ - INFO - Session ID: abc-123-def-456
2026-01-04 10:31:00 - __main__ - INFO - Selected model: gpt-5-mini
2026-01-04 10:31:00 - __main__ - INFO - Creating response placeholder
2026-01-04 10:31:00 - __main__ - INFO - Entered stream_agent_response async function
2026-01-04 10:31:00 - __main__ - INFO - About to call agent_service.stream_response()
2026-01-04 10:31:00 - services.agent_service - INFO - Stream response started for session abc-123-def-456
2026-01-04 10:31:00 - services.agent_service - DEBUG - Message: What is the network issue?...
2026-01-04 10:31:00 - services.agent_service - INFO - Starting agent.astream()...
2026-01-04 10:31:00 - services.agent_service - DEBUG - Calling agent.astream with message: What is the network issue?...
2026-01-04 10:31:01 - services.agent_service - DEBUG - Received chunk #1: <class 'dict'>
2026-01-04 10:31:01 - services.agent_service - DEBUG - Model response chunk: Let me analyze the network issue...
2026-01-04 10:31:01 - __main__ - INFO - UI received chunk #1, type: model
2026-01-04 10:31:02 - services.agent_service - DEBUG - Received chunk #2: <class 'dict'>
...
2026-01-04 10:31:10 - services.agent_service - INFO - Streaming complete. Total chunks: 15, Response length: 450
2026-01-04 10:31:10 - __main__ - INFO - Stream completed. Total chunks: 15
2026-01-04 10:31:10 - __main__ - INFO - run_async completed
2026-01-04 10:31:10 - __main__ - INFO - Status updated to complete
2026-01-04 10:31:10 - __main__ - INFO - About to rerun Streamlit
```

---

## Need Help?

If logs show errors you don't understand:
1. Copy the full error message and traceback
2. Check the log timestamps to see where it hangs
3. Share relevant log sections for debugging

**Most common hang point:** After "Starting agent.astream()..."
- This usually means the agent backend is not responding
- Check MCP server status first
- Verify API keys are valid in `~/.net-deepagent/creds.json`
