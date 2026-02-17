#!/usr/bin/env python3
"""
Integration test for SkillLearningMiddleware in the CLI loop
"""
import sys
import os
import asyncio
from unittest.mock import MagicMock, AsyncMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from net_deepagent_cli.agent import create_cli_agent, WrappedAgent
from net_deepagent_cli.loop import stream_agent_response
from net_deepagent_cli.ui import TerminalUI
from langchain_core.messages import AIMessage, HumanMessage

async def test_loop_integration():
    print("\n" + "="*60)
    print("TEST: Skill Learning Loop Integration")
    print("="*60)
    
    # 1. Mock the agent and middleware
    mock_agent = AsyncMock()
    mock_agent.astream = MagicMock()
    
    # Mock the skill learning middleware
    mock_learning_middleware = MagicMock()
    mock_learning_middleware.process_message = MagicMock()
    
    # Attach it to the agent (simulating what create_cli_agent does)
    mock_agent.skill_learning_middleware = mock_learning_middleware
    
    # 2. Mock UI
    mock_ui = MagicMock(spec=TerminalUI)
    mock_ui.show_progress.return_value.__enter__.return_value = MagicMock()
    
    # 3. Simulate agent response stream
    # The agent returns a chunk with messages
    test_message_content = "I found a Cisco 2960 switch at 192.168.1.50"
    
    async def mock_stream(*args, **kwargs):
        # First chunk - just thought
        yield {"messages": [HumanMessage(content="hi"), AIMessage(content="Thinking...")]}
        # Second chunk - actual content relevant to skills
        yield {"messages": [
            HumanMessage(content="hi"), 
            AIMessage(content="Thinking..."),
            AIMessage(content=test_message_content)
        ]}
    
    mock_agent.astream.side_effect = mock_stream
    
    # 4. Run the stream processor
    # We need a list that starts with just the human message
    messages = [HumanMessage(content="hi")]
    
    print("Streaming agent response...")
    await stream_agent_response(mock_agent, messages, mock_ui, auto_approve=True)
    
    # 5. Verify middleware was called
    print("\nVerifying middleware calls:")
    
    # It should have been called for the "Thinking..." message
    # AND the content message
    calls = mock_learning_middleware.process_message.call_args_list
    print(f"Total calls to process_message: {len(calls)}")
    
    found_content = False
    for call in calls:
        args = call[0][0] # First arg of call
        print(f"  Called with: {args}")
        if args.get('content') == test_message_content:
            found_content = True
            
    if found_content:
        print("\n✅ PASS: Middleware received the relevant message!")
        return 0
    else:
        print("\n❌ FAIL: Middleware did not receive the expected content.")
        return 1

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        sys.exit(loop.run_until_complete(test_loop_integration()))
    finally:
        loop.close()
