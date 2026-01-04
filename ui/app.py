import streamlit as st
import time
from datetime import datetime
import asyncio
import sys
from pathlib import Path
import uuid
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from services.agent_service import AgentService

logger.info("="*50)
logger.info("Streamlit UI Starting")
logger.info("="*50)

# Page configuration
st.set_page_config(
    page_title="AI Design Assistant",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern styling
st.markdown("""
<style>
    /* Main container styling */
    .main {
        background-color: #f8f9fa;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e0e0e0;
    }
    
    /* Chat message styling */
    .chat-message {
        padding: 1.2rem;
        border-radius: 12px;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    .user-message {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        margin-left: 20%;
    }
    
    .assistant-message {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        margin-right: 20%;
    }
    
    /* Custom button styling */
    .stButton>button {
        border-radius: 8px;
        border: none;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        font-weight: 500;
        padding: 0.6rem 1.2rem;
        transition: all 0.3s ease;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #ffffff;
        border-radius: 10px;
        padding: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 8px 16px;
        font-weight: 500;
    }
    
    /* File uploader styling */
    [data-testid="stFileUploader"] {
        background-color: #ffffff;
        border-radius: 10px;
        padding: 1rem;
        border: 2px dashed #e0e0e0;
    }
    
    /* Metric card styling */
    [data-testid="stMetricValue"] {
        font-size: 1.8rem;
        font-weight: 600;
        color: #667eea;
    }
    
    /* Header styling */
    h1 {
        color: #2c3e50;
        font-weight: 700;
    }
    
    h2, h3 {
        color: #34495e;
    }
    
    /* Success/info boxes */
    .stSuccess, .stInfo {
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)


# Helper functions for async operations
@st.cache_resource
def get_agent_service():
    """Initialize and return singleton AgentService."""
    logger.info("Getting AgentService singleton")
    service = AgentService()
    logger.info(f"AgentService instance: {service}")
    return service


def run_async(coro):
    """Run async coroutine in sync context."""
    logger.debug(f"Running async coroutine: {coro}")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(coro)
        logger.debug(f"Async coroutine completed successfully")
        return result
    except Exception as e:
        logger.error(f"Async coroutine failed: {e}", exc_info=True)
        raise
    finally:
        loop.close()


# Initialize AgentService
logger.info("Getting agent service...")
agent_service = get_agent_service()
logger.info(f"Agent service retrieved: {agent_service is not None}")

# Initialize agent on first run
if 'agent_initialized' not in st.session_state:
    logger.info("First run - initializing agent")
    with st.spinner("Initializing AI Agent..."):
        try:
            logger.info("Calling agent_service.initialize()...")
            run_async(agent_service.initialize())
            st.session_state.agent_initialized = True
            logger.info("Agent initialized successfully!")
        except Exception as e:
            logger.error(f"Failed to initialize agent: {str(e)}", exc_info=True)
            st.error(f"Failed to initialize agent: {str(e)}")
            st.stop()
else:
    logger.info("Agent already initialized")


# Initialize session state
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if 'selected_model' not in st.session_state:
    st.session_state.selected_model = agent_service.get_default_models()['main_model']
if 'uploaded_docs' not in st.session_state:
    st.session_state.uploaded_docs = []
if 'uploaded_diagrams' not in st.session_state:
    st.session_state.uploaded_diagrams = []

# Sidebar
with st.sidebar:
    st.title("🤖 Network AI Assistant")
    st.markdown("---")

    # Model selection
    st.subheader("⚙️ Model Selection")
    available_models = agent_service.get_available_models()
    selected_model = st.selectbox(
        "Main Model",
        options=available_models,
        index=available_models.index(st.session_state.selected_model) if st.session_state.selected_model in available_models else 0,
        help="Select the AI model to use for main agent"
    )
    if selected_model != st.session_state.selected_model:
        st.session_state.selected_model = selected_model

    st.markdown("---")

    # Upload sections
    st.subheader("📁 Upload Documents")
    
    design_doc = st.file_uploader(
        "Design Document",
        type=["pdf", "docx", "txt", "md"],
        help="Upload your design specification document",
        key="doc_uploader"
    )

    if design_doc and design_doc.name not in st.session_state.uploaded_docs:
        with st.spinner(f"Uploading {design_doc.name}..."):
            try:
                result = run_async(agent_service.upload_file(
                    design_doc,
                    design_doc.name,
                    "document",
                    st.session_state.session_id
                ))
                if result['success']:
                    st.success(f"✓ {design_doc.name}")
                    st.session_state.uploaded_docs.append(design_doc.name)
                else:
                    st.error(f"Upload failed: {result['message']}")
            except Exception as e:
                st.error(f"Error uploading: {str(e)}")

    st.markdown("<br>", unsafe_allow_html=True)

    network_diagram = st.file_uploader(
        "Network Diagram",
        type=["png", "jpg", "jpeg", "svg"],
        help="Upload your network architecture diagram",
        key="diagram_uploader"
    )

    if network_diagram and network_diagram.name not in st.session_state.uploaded_diagrams:
        with st.spinner(f"Uploading {network_diagram.name}..."):
            try:
                result = run_async(agent_service.upload_file(
                    network_diagram,
                    network_diagram.name,
                    "diagram",
                    st.session_state.session_id
                ))
                if result['success']:
                    st.success(f"✓ {network_diagram.name}")
                    st.session_state.uploaded_diagrams.append(network_diagram.name)

                    # Display preview
                    st.markdown("#### Preview:")
                    st.image(network_diagram, width=300, caption=network_diagram.name)
                else:
                    st.error(f"Upload failed: {result['message']}")
            except Exception as e:
                st.error(f"Error uploading: {str(e)}")
    
    st.markdown("---")
    
    # Quick stats
    st.subheader("📊 Session Stats")
    messages = agent_service.get_session_history(st.session_state.session_id)
    artifacts = agent_service.get_session_artifacts(st.session_state.session_id)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Messages", len(messages))
    with col2:
        st.metric("Artifacts", len(artifacts))

    st.markdown("<br>", unsafe_allow_html=True)

    # Session context info
    st.subheader("💬 Current Task")
    if len(messages) > 0:
        st.caption(f"🔗 Conversation has context ({len(messages)} messages)")
        st.caption(f"🆔 Session: ...{st.session_state.session_id[-8:]}")
    else:
        st.caption("🆕 New task - no messages yet")

    st.markdown("<br>", unsafe_allow_html=True)

    # New task button
    if st.button("🆕 New Task", use_container_width=True):
        agent_service.clear_session(st.session_state.session_id)
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.uploaded_docs = []
        st.session_state.uploaded_diagrams = []
        st.rerun()
    
    st.markdown("---")
    st.caption("Powered by Advanced AI • v2.0")

# Main content area
st.title("CoworkerX Workspace")

# Create main tabs
tab1, tab2, tab3, tab4 = st.tabs(["💬 Chat", "📦 Artifacts", "📡 Stream Logs", "⚠️ Errors"])

with tab1:
    # Chat interface
    st.markdown("### Conversation")

    # Get chat history from agent service
    chat_history = agent_service.get_session_history(st.session_state.session_id)

    # Chat history container
    chat_container = st.container()

    with chat_container:
        if not chat_history:
            st.info("👋 Start a conversation by asking about network issues, diagnostics, or configurations!")
        else:
            for message in chat_history:
                if message['role'] == 'user':
                    st.markdown(f"""
                    <div class="chat-message user-message">
                        <small style="opacity: 0.8;">{message['timestamp']}</small>
                        <div style="margin-top: 0.5rem;"><strong>You:</strong> {message['content']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="chat-message assistant-message">
                        <small style="opacity: 0.6;">{message['timestamp']}</small>
                        <div style="margin-top: 0.5rem;"><strong>Assistant:</strong> {message['content']}</div>
                    </div>
                    """, unsafe_allow_html=True)
    
    # Chat input area
    st.markdown("---")
    col1, col2 = st.columns([5, 1])
    
    with col1:
        user_input = st.text_input(
            "Type your message...",
            key="user_input",
            placeholder="Ask me anything about your design documents...",
            label_visibility="collapsed"
        )
    
    with col2:
        send_button = st.button("Send 📤", use_container_width=True)
    
    # Handle message sending
    if send_button and user_input:
        logger.info(f"Send button clicked. User input: {user_input[:100]}...")
        logger.info(f"Session ID: {st.session_state.session_id}")
        logger.info(f"Selected model: {st.session_state.selected_model}")

        # Process message with agent streaming
        with st.status("🤖 Agent is thinking...", expanded=True) as status:
            try:
                logger.info("Creating response placeholder")
                response_placeholder = st.empty()
                response_data = {"content": ""}  # Use dict to allow modification in nested function

                # Stream response from agent
                async def stream_agent_response():
                    logger.info("Entered stream_agent_response async function")
                    chunk_count = 0
                    try:
                        logger.info("About to call agent_service.stream_response()")
                        async for chunk in agent_service.stream_response(
                            user_input,
                            st.session_state.session_id,
                            st.session_state.selected_model
                        ):
                            chunk_count += 1
                            logger.info(f"UI received chunk #{chunk_count}, type: {chunk.get('type')}")

                            if chunk["type"] == "model" and chunk["content"]:
                                response_data["content"] += chunk["content"]
                                response_placeholder.markdown(response_data["content"] + "▌")
                                logger.debug(f"Updated UI with model content: {chunk['content'][:50]}...")

                            elif chunk["type"] == "tool":
                                tool_name = chunk.get("metadata", {}).get("tool_name", "unknown")
                                logger.info(f"Tool call displayed: {tool_name}")
                                st.write(f"🔧 Using tool: {tool_name}")

                            elif chunk["type"] == "error":
                                logger.error(f"Error chunk received: {chunk['content']}")
                                st.error(f"Error: {chunk['content']}")

                        logger.info(f"Stream completed. Total chunks: {chunk_count}")
                    except Exception as e:
                        logger.error(f"Error in stream_agent_response: {e}", exc_info=True)
                        raise

                # Run streaming
                logger.info("Calling run_async(stream_agent_response())")
                run_async(stream_agent_response())
                logger.info("run_async completed")

                # Remove cursor
                response_placeholder.markdown(response_data["content"])

                status.update(label="✅ Response complete!", state="complete")
                logger.info("Status updated to complete")

            except Exception as e:
                logger.error(f"Error processing message: {str(e)}", exc_info=True)
                st.error(f"Error processing message: {str(e)}")
                import traceback
                st.code(traceback.format_exc())

        logger.info("About to rerun Streamlit")
        st.rerun()

with tab2:
    # Artifacts view
    st.markdown("### Generated Artifacts")

    artifacts = agent_service.get_session_artifacts(st.session_state.session_id)

    if not artifacts:
        st.info("📦 No artifacts generated yet. Start chatting to create artifacts!")
    else:
        for idx, artifact in enumerate(artifacts):
            artifact_name = artifact.get('name', f'Artifact_{idx+1}')
            artifact_type = artifact.get('type', 'Unknown')
            artifact_timestamp = artifact.get('timestamp', 'N/A')
            artifact_content = artifact.get('content', '')
            artifact_lang = artifact.get('language', 'text')

            with st.expander(f"📄 {artifact_name} ({artifact_type}) - {artifact_timestamp}"):
                if artifact_type.startswith('code/'):
                    st.code(artifact_content, language=artifact_lang)
                else:
                    st.write(artifact_content)

                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"📥 Download", key=f"download_{idx}"):
                        st.download_button(
                            label="Download",
                            data=artifact_content,
                            file_name=f"{artifact_name}.txt",
                            mime="text/plain",
                            key=f"download_btn_{idx}"
                        )

with tab3:
    # Stream logs
    st.markdown("### Processing Stream Logs")

    stream_logs = agent_service.get_stream_logs(st.session_state.session_id)

    if not stream_logs:
        st.info("📡 No stream logs yet.")
    else:
        # Show most recent first
        for log in reversed(stream_logs):
            log_timestamp = log.get('timestamp', 'N/A')
            log_event = log.get('event', 'Unknown')
            log_details = log.get('details', '')

            st.markdown(f"""
            <div style="background-color: #f0f8ff; padding: 1rem; border-radius: 8px; margin-bottom: 0.5rem; border-left: 4px solid #667eea;">
                <strong>{log_timestamp}</strong> - {log_event}<br>
                <small style="opacity: 0.8;">{log_details}</small>
            </div>
            """, unsafe_allow_html=True)

with tab4:
    # Errors view
    st.markdown("### Error Logs")

    errors = agent_service.get_errors(st.session_state.session_id)

    if not errors:
        st.success("✅ No errors reported!")
    else:
        for error in errors:
            error_timestamp = error.get('timestamp', 'N/A')
            error_message = error.get('message', 'Unknown error')
            error_traceback = error.get('traceback', '')

            st.error(f"**{error_timestamp}** - {error_message}")
            if error_traceback:
                with st.expander("Details"):
                    st.code(error_traceback)

# Display uploaded files summary
uploaded_files = agent_service.get_uploaded_files(st.session_state.session_id)
if uploaded_files['documents'] or uploaded_files['diagrams']:
    st.markdown("---")
    st.subheader("📁 Uploaded Files")

    col1, col2 = st.columns(2)

    with col1:
        if uploaded_files['documents']:
            st.markdown("**📄 Documents:**")
            for doc in uploaded_files['documents']:
                st.caption(f"• {doc.get('filename', 'Unknown')}")

    with col2:
        if uploaded_files['diagrams']:
            st.markdown("**🖼️ Diagrams:**")
            for diagram in uploaded_files['diagrams']:
                st.caption(f"• {diagram.get('filename', 'Unknown')}")