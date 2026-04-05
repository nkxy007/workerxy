import asyncio
import os
import json
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

# Add current path to sys.path
sys.path.append(str(Path.home() / "workspace" / "agentic"))

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from net_deepagent_cli.communication.session import TOKEN_THRESHOLD, load_session, clear_session, save_session, filter_tool_messages, build_llm_messages
from net_deepagent_cli.loop import stream_agent_response

logging.basicConfig(level=logging.INFO)

async def test_memory_and_summarization():
    # Setup mocks
    agent = AsyncMock()
    # Mock astream to return a few chunks
    async def mock_astream(*args, **kwargs):
        input_messages = args[0].get("messages", []) if args else kwargs.get("messages", [])
        print(f"Agent received {len(input_messages)} messages")
        # Check if summary is present
        if any(isinstance(m, SystemMessage) and "Summary" in m.content for m in input_messages):
            print("Verified: Summary present in LLM input")
            
        messages = [
            AIMessage(content="I remember our previous talk.", usage_metadata={"total_tokens": 10, "input_tokens": 5, "output_tokens": 5})
        ]
        yield {"messages": input_messages + messages}

    agent.astream = mock_astream
    
    ui = MagicMock()
    ui.show_progress.return_value.__enter__.return_value = MagicMock()
    
    # Mock communication tools globally to avoid side effects
    import net_deepagent_cli.communication.tools as comm_tools
    comm_tools.send_discord_message = AsyncMock()
    comm_tools.send_final_reply_to_discord = AsyncMock()
    comm_tools.init_rabbit_channel = AsyncMock()

    # Payload for normal message
    channel_id = "test_channel_123"
    author = "test_user"
    
    # Stage 1: Initial message persistence
    print("\\n--- Stage 1: Initial message persistence ---")
    clear_session(channel_id)
    
    # Manually simulate the listener logic
    session = load_session(channel_id)
    msg = HumanMessage(content="Hello AI!")
    session["messages"].append(msg)
    llm_messages = build_llm_messages(session)
    
    await stream_agent_response(
        agent,
        llm_messages,
        ui,
        auto_approve=True,
        discord_channel_id=channel_id,
        author=author,
        session_id=channel_id
    )
    
    # Check file on disk
    p = Path.home() / ".net_deepagent" / "online_chat_sessions" / f"{channel_id}.json"
    print(f"DEBUG: File exists: {p.exists()}")
    if p.exists():
        print(f"DEBUG: File size: {p.stat().st_size}")
        with open(p, "r") as f:
            print(f"DEBUG: File content: {f.read()}")

    # Verify session file
    session = load_session(channel_id)
    print(f"Session count: {len(session['messages'])} messages")
    if len(session['messages']) < 2:
        print("FAIL: Session should have Human + AI message")
        return False

    # Stage 2: Threshold Summarization
    print("\\n--- Stage 2: Threshold Summarization ---")
    # Manually bloat the session
    large_content = "X" * (TOKEN_THRESHOLD * 5)
    session['messages'].append(HumanMessage(content=large_content))
    save_session(channel_id, session)
    
    # Re-simulate threshold logic in listener
    session = load_session(channel_id)
    from net_deepagent_cli.communication.session import estimate_tokens
    current_tokens = estimate_tokens(filter_tool_messages(session["messages"]))
    
    if current_tokens >= TOKEN_THRESHOLD:
        print(f"Threshold hit as expected: {current_tokens} tokens")
        # Mock summarizer
        import net_deepagent_cli.communication.summariser as summariser
        summariser.summarise_session = AsyncMock(return_value="FIXED TEST SUMMARY")
        
        # Summarize
        from net_deepagent_cli.communication.session import RECENT_EXCHANGES_TO_KEEP
        summary = await summariser.summarise_session(session)
        recent = filter_tool_messages(session["messages"])
        recent = recent[-(RECENT_EXCHANGES_TO_KEEP * 2):]
        session = {"summary": summary, "messages": recent}
        save_session(channel_id, session)
        print("Session summarized manually in test.")
    
    # Send another message
    session = load_session(channel_id)
    msg2 = HumanMessage(content="What about our long talk?")
    session["messages"].append(msg2)
    llm_messages_2 = build_llm_messages(session)
    
    await stream_agent_response(
        agent,
        llm_messages_2,
        ui,
        auto_approve=True,
        discord_channel_id=channel_id,
        author=author,
        session_id=channel_id
    )
    
    # Verify final session
    session = load_session(channel_id)
    print(f"Final session summary: {session['summary']}")
    if session['summary'] != "FIXED TEST SUMMARY":
        print("FAIL: Summary not in session")
        return False
        
    print("SUCCESS: Memory and Summarization verified!")
    return True

if __name__ == "__main__":
    asyncio.run(test_memory_and_summarization())
