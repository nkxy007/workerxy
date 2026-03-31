"""
Tests for the /bootup CLI command.
Run with:
    conda run -n test_langchain_env python -m pytest tests/test_bootup_command.py -v
"""
import unittest
import sys
import os
from unittest.mock import MagicMock, AsyncMock, patch, call

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import HumanMessage


class TestBootupCommand(unittest.IsolatedAsyncioTestCase):
    """Unit tests for /bootup command handler and registration."""

    def setUp(self):
        self.mock_ui = MagicMock()
        self.mock_ui.agent_name = "test_agent"
        self.mock_ui.console = MagicMock()
        self.mock_ui.print_message = MagicMock()
        self.mock_agent = MagicMock()

    # ------------------------------------------------------------------
    # 1. /bootup is listed in the COMMAND_STRUCTURE (appears in /help)
    # ------------------------------------------------------------------
    def test_help_lists_bootup(self):
        from net_deepagent_cli.ui import TerminalUI
        self.assertIn("/bootup", TerminalUI.COMMAND_STRUCTURE)
        desc = TerminalUI.COMMAND_STRUCTURE["/bootup"]["desc"]
        self.assertIsInstance(desc, str)
        self.assertTrue(len(desc) > 0)

    # ------------------------------------------------------------------
    # 2. handle_bootup appends a HumanMessage before calling stream_agent_response
    # ------------------------------------------------------------------
    async def test_bootup_appends_human_message(self):
        from net_deepagent_cli.commands import handle_bootup, BOOTUP_PROMPT

        messages = []

        with patch("net_deepagent_cli.loop.stream_agent_response", new_callable=AsyncMock) as mock_stream:
            await handle_bootup(self.mock_ui, messages, self.mock_agent)

        self.assertEqual(len(messages), 1)
        self.assertIsInstance(messages[0], HumanMessage)
        self.assertEqual(messages[0].content, BOOTUP_PROMPT)

    # ------------------------------------------------------------------
    # 3. handle_bootup calls stream_agent_response exactly once with auto_approve=True
    # ------------------------------------------------------------------
    async def test_bootup_calls_stream_once(self):
        from net_deepagent_cli.commands import handle_bootup

        messages = []

        with patch("net_deepagent_cli.loop.stream_agent_response", new_callable=AsyncMock) as mock_stream:
            await handle_bootup(self.mock_ui, messages, self.mock_agent)

        mock_stream.assert_called_once()
        _, kwargs = mock_stream.call_args
        self.assertTrue(kwargs.get("auto_approve", False))

    # ------------------------------------------------------------------
    # 4. /bootup via handle_command with no agent prints an error
    # ------------------------------------------------------------------
    async def test_bootup_no_agent_prints_error(self):
        from net_deepagent_cli.commands import handle_command

        messages = []
        with patch("net_deepagent_cli.loop.stream_agent_response", new_callable=AsyncMock) as mock_stream:
            await handle_command("/bootup", self.mock_ui, messages, agent=None)

        self.mock_ui.print_message.assert_called_once_with(
            "No agent attached to this session.", role="error"
        )
        mock_stream.assert_not_called()

    # ------------------------------------------------------------------
    # 5. /bootup via handle_command with a valid agent delegates to handle_bootup
    # ------------------------------------------------------------------
    async def test_bootup_with_agent_delegates(self):
        from net_deepagent_cli.commands import handle_command

        messages = []
        with patch("net_deepagent_cli.commands.handle_bootup", new_callable=AsyncMock) as mock_bootup:
            await handle_command("/bootup", self.mock_ui, messages, agent=self.mock_agent)

        mock_bootup.assert_called_once_with(self.mock_ui, messages, self.mock_agent)

    # ------------------------------------------------------------------
    # 6. BOOTUP_PROMPT contains the expected key topics
    # ------------------------------------------------------------------
    def test_bootup_prompt_covers_key_topics(self):
        from net_deepagent_cli.commands import BOOTUP_PROMPT
        self.assertIn("ready", BOOTUP_PROMPT.lower())
        self.assertIn("automat", BOOTUP_PROMPT.lower())
        self.assertIn("processes", BOOTUP_PROMPT.lower())
        self.assertIn("operator", BOOTUP_PROMPT.lower())


if __name__ == "__main__":
    unittest.main()
