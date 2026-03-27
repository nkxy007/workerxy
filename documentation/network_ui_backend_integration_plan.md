# Network Deep Agent UI Integration Plan

## Document Information
- **Created**: 2026-01-04
- **Purpose**: Plan for integrating the Streamlit UI (ui/app.py) with the net_deepagent.py backend
- **Status**: Ready for Review

---

## 1. Executive Summary

This plan outlines the integration of a Streamlit-based web UI with the existing net_deepagent.py backend. The backend uses LangGraph with multiple specialized subagents for network troubleshooting, design analysis, and cloud computing tasks. The UI will provide real-time interaction, streaming logs, artifact management, and evaluation metrics visualization.

---

## 2. Current State Analysis

### Backend (net_deepagent.py)
**Strengths:**
- Well-structured deep agent architecture with 4 specialized subagents:
  - `knowledge_acquisition_subagent`: Knowledge gathering from docs, internet, user clarification
  - `LAN_subagent`: LAN network routing/switching tasks
  - `network_design_subagent`: Design document and diagram analysis
  - `cloud_computing_subagent`: Cloud platform operations (AWS, Azure, GCP)
- Async streaming support via `astream()`
- MCP (Model Context Protocol) integration for network tools
- TruLens evaluation framework with 4 metrics:
  - Logical Consistency
  - Execution Efficiency
  - Plan Adherence
  - Plan Quality
- PII middleware for sensitive data masking
- Multiple LLM models (GPT-5, Claude-4, Gemini)

**Current Limitations:**
- Runs as standalone script (asyncio.run(main()))
- User interaction via command-line input()
- No API/service layer for external access
- Hardcoded questions in main()
- TruLens dashboard runs independently

### Frontend (ui/app.py)
**Strengths:**
- Modern, polished Streamlit UI with custom CSS
- 4-tab interface: Chat, Artifacts, Stream Logs, Errors
- File upload support (design docs, network diagrams)
- Session state management
- Responsive design with metrics display

**Current Limitations:**
- Mock/placeholder functionality only
- No backend connection
- Hardcoded responses
- No real streaming or agent interaction

---

## 3. Integration Architecture

### High-Level Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                      Streamlit UI                            │
│  ┌──────────┬───────────┬─────────────┬──────────────────┐ │
│  │   Chat   │ Artifacts │ Stream Logs │  Errors/Metrics  │ │
│  └──────────┴───────────┴─────────────┴──────────────────┘ │
└──────────────────┬──────────────────────────────────────────┘
                   │ Async Communication
                   │ (asyncio/threading)
┌──────────────────▼──────────────────────────────────────────┐
│            Backend Service Layer                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  AgentService: Manages agent lifecycle & streaming    │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│              Net Deep Agent (LangGraph)                      │
│  ┌────────────┬──────────────┬──────────────┬────────────┐ │
│  │ Knowledge  │ LAN Subagent │ Design Agent │ Cloud Agent│ │
│  │ Acquisition│              │              │            │ │
│  └────────────┴──────────────┴──────────────┴────────────┘ │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         MCP Client (Network Tools)                    │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│              TruLens Evaluation Layer                        │
│  Metrics: Logical Consistency, Execution Efficiency, etc.   │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Implementation Plan

### Phase 1: Backend Service Layer
**Goal**: Create a service wrapper around net_deepagent for UI consumption

**Files to Create/Modify:**
- `services/agent_service.py` (NEW)
- `net_deepagent.py` (MODIFY)

**Key Tasks:**
1. **Extract agent initialization into reusable function**
   - Move agent creation logic from `main()` into `create_network_agent()` function
   - Make it configurable (models, tools, subagents)
   - Support singleton pattern for reuse across requests

2. **Create AgentService class** (`services/agent_service.py`)
   ```python
   class AgentService:
       - __init__(): Initialize agent, MCP client, TruLens
       - async process_message(message, session_id): Process user queries
       - async stream_response(message, session_id): Stream agent responses
       - get_session_history(session_id): Retrieve chat history
       - get_evaluation_metrics(session_id): Get TruLens metrics
       - upload_document(file, doc_type): Handle file uploads
       - clear_session(session_id): Reset session state
   ```

3. **Handle file uploads**
   - Accept design documents (PDF, DOCX, TXT)
   - Accept network diagrams (PNG, JPG, SVG)
   - Store files temporarily
   - Pass file paths/content to relevant subagents (network_design_subagent)

4. **Session management**
   - Support multiple concurrent user sessions
   - Use session_id for isolation
   - Maintain separate message histories per session

5. **User clarification handling**
   - Replace `input()` in `user_clarification_and_action_tool` with callback mechanism
   - Queue clarification requests for UI to display
   - Accept responses from UI and continue processing

### Phase 2: UI Backend Integration
**Goal**: Connect Streamlit UI to AgentService

**Files to Modify:**
- `ui/app.py` (MAJOR MODIFICATIONS)

**Key Tasks:**
1. **Initialize AgentService in Streamlit**
   - Create singleton instance using `@st.cache_resource`
   - Handle async initialization properly
   - Generate unique session_id for each browser session

2. **Replace mock chat with real agent streaming**
   - Remove mock response generation
   - Call `AgentService.stream_response()` on message send
   - Display streaming chunks in real-time
   - Use `st.status()` or `st.spinner()` for progress indication

3. **Implement file upload handling**
   - Pass uploaded files to `AgentService.upload_document()`
   - Store file references in session state
   - Display upload confirmation with file details

4. **Real-time stream logs**
   - Capture agent processing events:
     - Subagent invocations
     - Tool calls
     - Model responses
     - Errors/retries
   - Display in Stream Logs tab with timestamps
   - Auto-scroll to latest log

5. **Artifact management**
   - Detect artifacts in agent responses:
     - Configuration files
     - Command outputs
     - Analysis reports
     - Diagrams/visualizations
   - Parse and store in session state
   - Display in Artifacts tab with download buttons

6. **Error handling**
   - Catch exceptions from AgentService
   - Display user-friendly error messages
   - Log full tracebacks in Errors tab
   - Allow retry mechanism

7. **User clarification flow**
   - Detect when agent requests clarification
   - Display modal/form for user input
   - Send response back to agent
   - Resume processing seamlessly

### Phase 3: Evaluation Metrics Integration
**Goal**: Display TruLens metrics in UI

**Files to Modify:**
- `ui/app.py` (ADD METRICS TAB/SECTION)

**Key Tasks:**
1. **Add Metrics tab/section**
   - Create new tab "Evaluation Metrics"
   - Display 4 TruLens metrics with scores
   - Show chain-of-thought reasoning for each metric

2. **Real-time metrics updates**
   - Poll `AgentService.get_evaluation_metrics()` after responses
   - Display loading state while metrics compute
   - Refresh metrics display automatically

3. **Metrics visualization**
   - Use `st.metric()` for score display
   - Color-code scores (red/yellow/green)
   - Show trend indicators if available
   - Expandable sections for detailed reasoning

4. **Historical metrics**
   - Store metrics per conversation
   - Display metrics history over session
   - Allow comparison between queries

### Phase 4: Advanced Features
**Goal**: Polish and enhance user experience

**Key Tasks:**
1. **Streaming UI improvements**
   - Stream text token-by-token for better UX
   - Show "thinking..." indicators per subagent
   - Display tool call notifications ("Calling SSH tool...")

2. **Network diagram integration**
   - Pass uploaded diagrams to `network_design_subagent`
   - Display diagram with annotations from agent
   - Support diagram-based queries ("What's wrong with this switch?")

3. **Export functionality**
   - Export conversation as JSON/Markdown
   - Download artifacts as ZIP
   - Export metrics as CSV/PDF report

4. **Configuration panel**
   - Allow model selection (GPT-5 vs GPT-4 vs Claude)
   - Toggle subagents on/off
   - Adjust thinking effort level
   - PII masking settings

5. **Multi-session support**
   - Session history dropdown
   - Save/load previous sessions
   - Compare sessions side-by-side

---

## 5. Technical Implementation Details

### 5.1 Async Integration with Streamlit
**Challenge**: Streamlit is synchronous, but net_deepagent uses async

**Solution**:
```python
import asyncio
import streamlit as st
from concurrent.futures import ThreadPoolExecutor

# Option 1: Run async in thread pool
@st.cache_resource
def get_agent_service():
    return AgentService()

def process_message_sync(message):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(
        agent_service.process_message(message)
    )
    loop.close()
    return result

# Option 2: Use streamlit-async or similar library
```

### 5.2 Streaming Implementation
**Approach**:
```python
async def stream_to_ui(message, placeholder):
    response_chunks = []
    async for chunk in agent_service.stream_response(message):
        # Extract message from chunk
        if "messages" in chunk.get("model", ""):
            content = chunk["model"]["messages"][-1].content
            response_chunks.append(content)
            # Update UI progressively
            placeholder.markdown("".join(response_chunks))

        # Log tool calls
        if "messages" in chunk.get("tools", ""):
            tool_msg = chunk["tools"]["messages"][-1]
            log_stream_event(f"Tool: {tool_msg.name}")

    return "".join(response_chunks)
```

### 5.3 File Upload Flow
```
1. User uploads file in sidebar
2. Streamlit receives file as BytesIO
3. Save temporarily to disk: /tmp/agentic_uploads/{session_id}/{filename}
4. Pass file path to AgentService.upload_document()
5. AgentService:
   - For design docs: Extract text, store in agent context
   - For diagrams: Pass to network_design_subagent via MCP tools
6. Confirm upload to user
7. Agent can now reference uploaded content
```

### 5.4 User Clarification Mechanism
**Current (Command-line)**:
```python
response = input("Please provide clarification: ")
```

**Proposed (UI)**:
```python
# In user_clarification_and_action_tool
if st.session_state.get('clarification_queue'):
    # Display pending questions
    question = st.session_state.clarification_queue[0]
    with st.form("clarification_form"):
        st.warning(f"Agent needs info: {question}")
        answer = st.text_input("Your answer:")
        submit = st.form_submit_button("Submit")
        if submit:
            # Send answer back to agent via queue
            st.session_state.clarification_responses.append(answer)
            st.session_state.clarification_queue.pop(0)
            st.rerun()
```

### 5.5 Session Management
```python
# Generate session ID
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# Pass to all agent calls
agent_service.process_message(
    message=user_input,
    session_id=st.session_state.session_id
)
```

---

## 6. File Structure

### New Files
```
agentic/
├── services/
│   ├── __init__.py
│   └── agent_service.py          # NEW: Backend service layer
├── utils/
│   ├── __init__.py
│   ├── file_handler.py           # NEW: File upload utilities
│   └── session_manager.py        # NEW: Session management
├── uploads/                      # NEW: Temporary file storage
└── network_ui_backend_integration_plan.md  # THIS FILE
```

### Modified Files
```
agentic/
├── net_deepagent.py              # MODIFY: Extract to service layer
├── ui/
│   └── app.py                    # MODIFY: Integrate with backend
└── prompts.py                    # Potentially modify for context
```

---

## 7. Key Integration Points

### 7.1 Message Flow
```
User types message in UI
    ↓
Streamlit captures input
    ↓
Call AgentService.stream_response(message, session_id)
    ↓
AgentService invokes net_deep_agent.astream()
    ↓
Stream chunks back to UI
    ↓
Update chat display in real-time
    ↓
Store final response in chat history
    ↓
Extract artifacts, update metrics
```

### 7.2 Subagent Visibility
```
Agent decides to invoke LAN_subagent
    ↓
Emit event: "Invoking LAN Subagent"
    ↓
UI displays in Stream Logs: "🔧 LAN Subagent activated"
    ↓
Subagent calls tool (e.g., SSH)
    ↓
UI displays: "📡 Executing SSH command on 192.168.1.1"
    ↓
Subagent returns result
    ↓
UI displays: "✅ LAN Subagent completed"
```

### 7.3 Evaluation Metrics Flow
```
Agent completes processing
    ↓
TruLens evaluates trace
    ↓
Compute 4 metrics (async, may take 5-10s)
    ↓
AgentService.get_evaluation_metrics() returns scores
    ↓
UI displays in Metrics section with reasoning
```

---

## 8. Error Handling Strategy

### Types of Errors
1. **Agent Errors**: Tool failures, model errors, subagent crashes
2. **Network Errors**: MCP connection failures, API timeouts
3. **File Errors**: Upload failures, parsing errors
4. **Session Errors**: State corruption, concurrency issues

### Handling Approach
```python
try:
    async for chunk in agent_service.stream_response(message):
        # Process chunk
except ToolCallError as e:
    st.error(f"Tool call failed: {e.tool_name}")
    st.session_state.errors.append({
        'timestamp': now(),
        'type': 'ToolCallError',
        'message': str(e),
        'traceback': traceback.format_exc()
    })
except MCPConnectionError as e:
    st.error("Network tools unavailable. Check MCP server.")
except Exception as e:
    st.error("An unexpected error occurred. Check Errors tab.")
    log_error(e)
```

---

## 9. Testing Strategy

### Unit Tests
- `agent_service.py`: Test message processing, file uploads, session management
- `file_handler.py`: Test file validation, storage, cleanup
- Modified tools: Test new callback mechanisms

### Integration Tests
- End-to-end flow: User message → Agent → Response → UI display
- File upload → Agent processing → Diagram analysis
- User clarification request → UI prompt → Response → Agent resume
- Metrics computation → UI display

### Manual Testing Scenarios
1. **Basic chat**: Ask simple network question, verify response
2. **File upload**: Upload diagram, ask diagram-specific question
3. **Streaming**: Verify real-time updates during long responses
4. **Subagent invocation**: Trigger each subagent, verify logs
5. **Error handling**: Force errors, verify graceful degradation
6. **Multi-session**: Open 2 browser tabs, verify isolation
7. **Clarification flow**: Trigger user_clarification_tool, respond in UI
8. **Metrics display**: Verify all 4 TruLens metrics appear

---

## 10. Deployment Considerations

### Environment Variables
```bash
# Required
OPENAI_API_KEY=xxx
ANTHROPIC_API_KEY=xxx
GEMINI_API_KEY=xxx

# Optional
MCP_SERVER_URL=http://localhost:8000/mcp
UPLOAD_DIR=/tmp/agentic_uploads
SESSION_TIMEOUT=3600
```

### Docker Setup (Optional)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "ui/app.py", "--server.port=8501"]
```

### Performance Optimization
- Cache agent initialization with `@st.cache_resource`
- Use connection pooling for MCP client
- Implement response caching for repeated queries
- Compress uploaded files
- Lazy-load TruLens dashboard

---

## 11. Security Considerations

### Data Privacy
- PII masking for IPs, MACs, hostnames (already in backend)
- Secure file upload validation (file type, size limits)
- Clear uploads after session timeout
- No persistent storage of sensitive data

### Access Control
- Consider adding authentication (Streamlit auth, OAuth)
- Rate limiting for API calls
- Input validation/sanitization

---

## 12. Success Criteria

### Must Have (MVP)
- ✅ Users can chat with agent via UI
- ✅ Agent responses stream in real-time
- ✅ File uploads (docs, diagrams) work
- ✅ Stream logs show subagent activity
- ✅ Errors display with details
- ✅ Basic artifacts captured

### Should Have
- ✅ TruLens metrics display
- ✅ User clarification flow works
- ✅ Multi-session support
- ✅ Export conversation/artifacts

### Nice to Have
- Model selection in UI
- Session history/comparison
- Advanced metrics visualization
- Real-time TruLens dashboard embedding

---

## 13. Timeline Breakdown

### Phase 1: Backend Service Layer
**Tasks:**
- Extract agent initialization
- Create AgentService class
- Implement session management
- File upload handling
- User clarification mechanism

### Phase 2: UI Integration
**Tasks:**
- Connect UI to AgentService
- Real streaming implementation
- Stream logs integration
- Artifacts extraction
- Error handling

### Phase 3: Metrics Integration
**Tasks:**
- Metrics tab creation
- TruLens integration
- Visualization components
- Historical metrics

### Phase 4: Polish
**Tasks:**
- Advanced streaming UX
- Export functionality
- Configuration panel
- Testing and bug fixes

---

## 14. Risk Mitigation

### Identified Risks
1. **Async/Sync mismatch**: Streamlit + async agent
   - Mitigation: Thread pool executor, tested patterns

2. **Performance degradation**: Multiple concurrent sessions
   - Mitigation: Connection pooling, caching, timeouts

3. **User clarification deadlock**: Agent waits for input, UI frozen
   - Mitigation: Non-blocking queue mechanism, timeouts

4. **File upload security**: Malicious files
   - Mitigation: Strict validation, sandboxed processing

5. **Metrics computation delay**: TruLens takes 5-10s
   - Mitigation: Async computation, loading indicators, optional feature

---

## 15. Next Steps

1. **Review this plan** with stakeholders
2. **Clarify requirements**: Any missing features or priorities?
3. **Create detailed task breakdown** for Phase 1
4. **Set up development branch**
5. **Begin Phase 1 implementation**

---

## 16. Questions for Review

1. **Priority**: Which phase should we start with? (Recommend: Phase 1 → Phase 2) Phase 1 then Phase 2 but make sure the net_deepagant.py can also be launched using python in that case it can use a if __name__=="__main__"
2. **Scope**: Are all features necessary for MVP, or can we defer some to later? Trulens metrics on UI will be done in another phase
3. **Models**: Should UI allow users to select which LLM to use? for different models mentioned in net_deepagent.py we can allow selection with a default model as the one in that document
4. **Authentication**: Do we need user authentication, or is this internal tool? Any authentication will be done on its own section later.
5. **Metrics**: Is TruLens integration critical for MVP, or can it be Phase 3+? yes in phase 3+
6. **MCP Server**: Is the network MCP server already running and accessible? yes
7. **File Storage**: Temporary vs persistent file storage for uploads? lets create a directory called user_chat_files and it will be used for uploads and temporary files
8. **Deployment**: Local Streamlit or production deployment target? local streamlit for now

---

## Appendix A: Dependencies

### Additional Python Packages Needed
```
# Current (from net_deepagent.py)
langgraph
langchain-core
langchain-openai
langchain-anthropic
langchain-google-genai
langchain-mcp-adapters
trulens-core
trulens-providers-openai
trulens-apps-langgraph
deepagents
pydantic

# New for UI integration
streamlit
python-multipart  # For file uploads
aiofiles           # For async file I/O
uuid               # For session IDs (stdlib)
```

### System Requirements
- Python 3.11+
- MCP server running (http://localhost:8000/mcp)
- Sufficient API credits (OpenAI, Anthropic, Google)
- TruLens database storage

---

## Appendix B: Code Snippets

### AgentService Structure (Skeleton)
```python
# services/agent_service.py
from typing import AsyncIterator, Dict, Any
import uuid
from net_deepagent import create_network_agent

class AgentService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    async def initialize(self):
        if not self._initialized:
            self.agent = await create_network_agent()
            self.sessions = {}
            self._initialized = True

    async def stream_response(
        self,
        message: str,
        session_id: str
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream agent response chunks"""
        if session_id not in self.sessions:
            self.sessions[session_id] = {"messages": []}

        async for chunk in self.agent.astream({"messages": message}):
            yield chunk

    def get_session_history(self, session_id: str):
        """Retrieve chat history for session"""
        return self.sessions.get(session_id, {}).get("messages", [])

    async def upload_document(self, file_data, file_type, session_id):
        """Handle document uploads"""
        # Save file, process, add to context
        pass

    async def get_evaluation_metrics(self, session_id: str):
        """Get TruLens metrics for session"""
        # Query TruLens for metrics
        pass
```

### Streamlit Integration (Skeleton)
```python
# ui/app.py modifications
import streamlit as st
from services.agent_service import AgentService
import asyncio

@st.cache_resource
def init_agent_service():
    service = AgentService()
    asyncio.run(service.initialize())
    return service

agent_service = init_agent_service()

# In chat handler
if send_button and user_input:
    with st.spinner("Processing..."):
        # Run async in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        response_placeholder = st.empty()
        full_response = ""

        async def stream():
            nonlocal full_response
            async for chunk in agent_service.stream_response(
                user_input,
                st.session_state.session_id
            ):
                # Process chunk
                if "messages" in chunk.get("model", ""):
                    content = chunk["model"]["messages"][-1].content
                    full_response += content
                    response_placeholder.markdown(full_response)

        loop.run_until_complete(stream())
        loop.close()
```

---

**End of Plan**

This document is ready for review and discussion. Please provide feedback on priorities, scope, and any additional requirements.
