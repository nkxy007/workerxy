"""
Unit tests for utils/session_archiver.py

Run with:
    conda activate test_langchain_env
    cd /path/to/workerxy
    python -m pytest tests/test_session_archiver.py -v
"""

import asyncio
import sys
import os
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage


class TestFilterForArchive(unittest.TestCase):
    """Tests for the _filter_for_archive helper."""

    def _call(self, messages):
        from utils.session_archiver import _filter_for_archive
        return _filter_for_archive(messages)

    def test_keeps_human_and_ai_messages(self):
        msgs = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there"),
        ]
        result = self._call(msgs)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], {"role": "user", "content": "Hello"})
        self.assertEqual(result[1], {"role": "assistant", "content": "Hi there"})

    def test_filters_out_tool_messages(self):
        msgs = [
            HumanMessage(content="Run a ping"),
            AIMessage(content="", tool_calls=[{"name": "ping", "args": {}, "id": "1"}]),
            ToolMessage(content="PING 8.8.8.8: 56 bytes", tool_call_id="1"),
            AIMessage(content="The ping succeeded."),
        ]
        result = self._call(msgs)
        # Only the human + final AI text should survive
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["role"], "user")
        self.assertEqual(result[1]["role"], "assistant")
        self.assertEqual(result[1]["content"], "The ping succeeded.")

    def test_filters_out_system_messages(self):
        msgs = [
            SystemMessage(content="You are a helpful assistant."),
            HumanMessage(content="Hello"),
            AIMessage(content="Hi"),
        ]
        result = self._call(msgs)
        self.assertEqual(len(result), 2)
        self.assertFalse(any(r["role"] == "system" for r in result))

    def test_filters_ai_tool_dispatch_messages(self):
        """AI messages with tool_calls but NO text content must be excluded."""
        msgs = [
            HumanMessage(content="What's the weather?"),
            AIMessage(content="", tool_calls=[{"name": "get_weather", "args": {}, "id": "2"}]),
            AIMessage(content="It's sunny!"),
        ]
        result = self._call(msgs)
        self.assertEqual(len(result), 2)
        # The blank AI dispatch message should not be in results
        self.assertEqual(result[1]["content"], "It's sunny!")

    def test_filters_empty_content(self):
        msgs = [
            HumanMessage(content="   "),  # whitespace only
            AIMessage(content=""),         # empty
            HumanMessage(content="Real question"),
        ]
        result = self._call(msgs)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["content"], "Real question")

    def test_mixed_scenario(self):
        """Full realistic scenario with all message types."""
        msgs = [
            SystemMessage(content="You are an agent."),
            HumanMessage(content="Check the router"),
            AIMessage(content="", tool_calls=[{"name": "ssh_tool", "args": {}, "id": "3"}]),
            ToolMessage(content="show ip int brief output...", tool_call_id="3"),
            AIMessage(content="The router interfaces are all up."),
        ]
        result = self._call(msgs)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["role"], "user")
        self.assertEqual(result[1]["role"], "assistant")
        self.assertEqual(result[1]["content"], "The router interfaces are all up.")


class TestArchiveSessionAsync(unittest.IsolatedAsyncioTestCase):
    """Tests for the async archive_session_async coroutine."""

    @patch("utils.session_archiver.ArchiverRetriever")
    async def test_archive_called_with_correct_args(self, MockArchiver):
        """ArchiverRetriever.archive_conversation receives filtered messages + metadata."""
        mock_instance = MagicMock()
        mock_instance.archive_conversation.return_value = "doc_123"
        MockArchiver.return_value = mock_instance

        from utils.session_archiver import archive_session_async
        msgs = [HumanMessage(content="Hello"), AIMessage(content="World")]
        result = await archive_session_async(msgs, "test_session")

        self.assertEqual(result, "doc_123")
        mock_instance.archive_conversation.assert_called_once()
        call_args = mock_instance.archive_conversation.call_args
        # First positional arg should be the filtered list
        filtered = call_args[0][0]
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0]["role"], "user")
        # Metadata should contain session_name
        metadata = call_args[1]["metadata"]
        self.assertEqual(metadata["session_name"], "test_session")
        self.assertEqual(metadata["source"], "cli_session_save")

    @patch("utils.session_archiver.ArchiverRetriever")
    async def test_returns_none_for_empty_filtered_messages(self, MockArchiver):
        """If all messages are filtered out, archive_conversation should NOT be called."""
        from utils.session_archiver import archive_session_async
        msgs = [
            ToolMessage(content="tool output", tool_call_id="x"),
            SystemMessage(content="sys"),
        ]
        result = await archive_session_async(msgs, "empty_session")
        self.assertIsNone(result)
        MockArchiver.return_value.archive_conversation.assert_not_called()

    @patch("utils.session_archiver.ArchiverRetriever", side_effect=Exception("No API key"))
    async def test_handles_archiver_init_failure_gracefully(self, _MockArchiver):
        """If ArchiverRetriever raises on init, return None without propagating."""
        from utils.session_archiver import archive_session_async
        msgs = [HumanMessage(content="Hello"), AIMessage(content="Hi")]
        result = await archive_session_async(msgs, "fail_session")
        self.assertIsNone(result)

    @patch("utils.session_archiver.ArchiverRetriever")
    async def test_handles_archive_conversation_failure_gracefully(self, MockArchiver):
        """If archive_conversation raises, return None without propagating."""
        mock_instance = MagicMock()
        mock_instance.archive_conversation.side_effect = Exception("ChromaDB error")
        MockArchiver.return_value = mock_instance

        from utils.session_archiver import archive_session_async
        msgs = [HumanMessage(content="Hello"), AIMessage(content="Hi")]
        result = await archive_session_async(msgs, "error_session")
        self.assertIsNone(result)


class TestFireAndForgetArchive(unittest.IsolatedAsyncioTestCase):
    """Tests for the fire_and_forget_archive wrapper."""

    @patch("utils.session_archiver.ArchiverRetriever")
    async def test_fire_and_forget_creates_task_and_does_not_block(self, MockArchiver):
        """fire_and_forget_archive should return immediately (not await)."""
        mock_instance = MagicMock()
        mock_instance.archive_conversation.return_value = "doc_ff"
        MockArchiver.return_value = mock_instance

        from utils.session_archiver import fire_and_forget_archive
        msgs = [HumanMessage(content="Test"), AIMessage(content="Response")]

        # Simply calling it should not raise and should not block
        fire_and_forget_archive(msgs, "ff_session")

        # Give the event loop a chance to run the scheduled task
        await asyncio.sleep(0)
        await asyncio.sleep(0)  # Two yields to let the task complete

        mock_instance.archive_conversation.assert_called_once()


if __name__ == "__main__":
    unittest.main()
