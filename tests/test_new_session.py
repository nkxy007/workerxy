import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path
import json
import shutil
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from net_deepagent_cli.commands import handle_command
from langchain_core.messages import HumanMessage, AIMessage

class TestNewSession(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_ui = MagicMock()
        self.mock_ui.agent_name = "test_agent"
        # Setup sessions dir
        self.test_sessions_dir = Path.home() / ".net-deepagent" / "test_agent" / "sessions"
        self.test_sessions_dir.mkdir(parents=True, exist_ok=True)
        self.mock_ui.console = MagicMock()
        self.mock_ui.confirm = AsyncMock(return_value=True)
        self.mock_ui.prompt_simple = AsyncMock()
        
    def tearDown(self):
        if self.test_sessions_dir.parent.exists():
            shutil.rmtree(self.test_sessions_dir.parent)

    async def test_session_new_empty_no_prompt(self):
        messages = []
        await handle_command("/session new", self.mock_ui, messages)
        self.assertEqual(len(messages), 0)
        self.mock_ui.print_message.assert_any_call("✨ [bold green]New session started.[/bold green]", role="system")

    async def test_session_new_no_save(self):
        messages = [HumanMessage(content="Hello"), AIMessage(content="Hi")]
        self.mock_ui.confirm.return_value = False
        
        await handle_command("/session new", self.mock_ui, messages)
        
        self.assertEqual(len(messages), 0)
        self.mock_ui.print_message.assert_any_call("✨ [bold green]New session started.[/bold green]", role="system")

    async def test_session_new_with_save(self):
        messages = [HumanMessage(content="Hello"), AIMessage(content="Hi")]
        self.mock_ui.confirm.return_value = True
        self.mock_ui.prompt_simple.return_value = "test_save"
        
        await handle_command("/session new", self.mock_ui, messages)
        
        self.assertEqual(len(messages), 0)
        save_file = self.test_sessions_dir / "test_save.json"
        self.assertTrue(save_file.exists())
        
        with open(save_file, 'r') as f:
            data = json.load(f)
            self.assertEqual(len(data), 2)
            self.assertEqual(data[0]['data']['content'], "Hello")

    async def test_session_new_with_full_yes_save(self):
        messages = [HumanMessage(content="Hello"), AIMessage(content="Hi")]
        self.mock_ui.confirm.return_value = True
        self.mock_ui.prompt_simple.return_value = "test_save_yes"
        
        await handle_command("/session new", self.mock_ui, messages)
        
        self.assertEqual(len(messages), 0)
        save_file = self.test_sessions_dir / "test_save_yes.json"
        self.assertTrue(save_file.exists())

    async def test_session_new_cancel_save(self):
        messages = [HumanMessage(content="Hello"), AIMessage(content="Hi")]
        self.mock_ui.confirm.return_value = True
        self.mock_ui.prompt_simple.return_value = ""
        
        await handle_command("/session new", self.mock_ui, messages)
        
        # It should still clear the session as they asked for a "new" one
        self.assertEqual(len(messages), 0)
        self.mock_ui.print_message.assert_any_call("Save cancelled (no name provided).", role="warning")
        self.mock_ui.print_message.assert_any_call("✨ [bold green]New session started.[/bold green]", role="system")

    async def test_session_delete_with_name(self):
        # Create a session to delete
        session_file = self.test_sessions_dir / "delete_me.json"
        session_file.write_text("[]")
        
        # User provides name in command and confirms
        self.mock_ui.confirm.return_value = True
        
        await handle_command("/session delete delete_me", self.mock_ui, [])
        
        self.assertFalse(session_file.exists())
        self.mock_ui.print_message.assert_any_call("Session [bold cyan]delete_me.json[/bold cyan] deleted successfully.", role="system")

    async def test_session_delete_with_prompt(self):
        # Create a session to delete
        session_file = self.test_sessions_dir / "prompt_delete.json"
        session_file.write_text("[]")
        
        # User provides no name, prompts for 'prompt_delete' then confirms
        self.mock_ui.prompt_simple.return_value = "prompt_delete"
        self.mock_ui.confirm.return_value = True
        
        await handle_command("/session delete", self.mock_ui, [])
        
        self.assertFalse(session_file.exists())

    async def test_session_delete_cancel(self):
        # Create a session to NOT delete
        session_file = self.test_sessions_dir / "keep_me.json"
        session_file.write_text("[]")
        
        # User provides name and cancels
        self.mock_ui.confirm.return_value = False
        
        await handle_command("/session delete keep_me", self.mock_ui, [])
        
        self.assertTrue(session_file.exists())
        self.mock_ui.print_message.assert_any_call("Deletion cancelled.", role="system")

if __name__ == "__main__":
    unittest.main()
