import asyncio
import sys
from pathlib import Path
import json
from unittest.mock import MagicMock, AsyncMock

# Add current path to sys.path
sys.path.append(str(Path.home() / "workspace" / "agentic"))

from langchain_core.messages import HumanMessage, AIMessage
from net_deepagent_cli.loop import stream_agent_response

import logging
logging.basicConfig(level=logging.INFO)

async def test_session_saving():
    # Setup mocks
    agent = AsyncMock()
    
    async def mock_astream(*args, **kwargs):
        input_messages = args[0].get("messages", []) if args else kwargs.get("messages", [])
        messages = [
            AIMessage(
                content="This is a test response", 
                usage_metadata={"total_tokens": 10, "input_tokens": 5, "output_tokens": 5}
            )
        ]
        yield {"messages": input_messages + messages}

    agent.astream = mock_astream
    
    ui = MagicMock()
    ui.show_progress.return_value.__enter__.return_value = MagicMock()

    author_name = "test_user_fallback"
    channel_name = "test_channel_fallback"

    messages_list = [HumanMessage(content="Hello for fallback session")]

    try:
        await stream_agent_response(
            agent,
            messages_list,
            ui,
            auto_approve=True,
            author=author_name,
            channel_name=channel_name
            # Not providing session_id or discord_channel_id to test the fallback branch
        )
    except Exception as e:
        print(f"Error during stream_agent_response: {e}")

    # Check file on disk
    base_dir = Path.home() / ".net_deepagent" / "online_chat_sessions" / author_name
    print(f"DEBUG: Checking directory {base_dir}")
    if base_dir.exists():
        files = list(base_dir.glob("*.json"))
        if files:
            print(f"SUCCESS: Found saved session file(s): {files}")
            return True
        else:
            print("FAIL: No JSON files found in author directory.")
            return False
    else:
        print("FAIL: Author directory does not exist.")
        return False

if __name__ == "__main__":
    asyncio.run(test_session_saving())
