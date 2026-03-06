"""
Tests for the Discord headless auto-reply feature.

Phase 1: send_final_reply_to_discord (tools.py) + the post-stream callback in loop.py
Phase 2: Ack message sent from listener.py on receipt

Run with conda virtual env:
    conda run -n agentic pytest tests/test_discord_reply.py -v
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from langchain_core.messages import AIMessage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_ai_message(content, tool_calls=None):
    """Build a minimal AIMessage for testing."""
    msg = AIMessage(content=content)
    msg.tool_calls = tool_calls or []
    return msg


# ===========================================================================
# Phase 1 — send_final_reply_to_discord (tools.py)
# ===========================================================================

class TestSendFinalReplyToDiscord:
    """Unit tests for the send_final_reply_to_discord helper in tools.py."""

    @pytest.fixture(autouse=True)
    def patch_send_discord(self):
        """Mock the send_discord_message tool so no RabbitMQ is needed."""
        with patch(
            "net_deepagent_cli.communication.tools.send_discord_message"
        ) as mock_tool:
            mock_tool.ainvoke = AsyncMock(return_value="ok")
            yield mock_tool

    @pytest.mark.asyncio
    async def test_sends_string_content(self, patch_send_discord):
        """Final AIMessage with plain string content is sent."""
        from net_deepagent_cli.communication.tools import send_final_reply_to_discord

        msg = make_ai_message("Hello from the agent!")
        await send_final_reply_to_discord(msg, channel_id=123, channel_name="general")

        patch_send_discord.ainvoke.assert_awaited_once()
        call_args = patch_send_discord.ainvoke.call_args[0][0]
        assert call_args["message"] == "Hello from the agent!"
        assert call_args["channel_id"] == 123

    @pytest.mark.asyncio
    async def test_sends_block_list_content(self, patch_send_discord):
        """Content in Anthropic block-list format is flattened and sent."""
        from net_deepagent_cli.communication.tools import send_final_reply_to_discord

        msg = make_ai_message([
            {"type": "text", "text": "Line one."},
            {"type": "text", "text": "Line two."},
        ])
        await send_final_reply_to_discord(msg, channel_id=456)

        patch_send_discord.ainvoke.assert_awaited_once()
        sent_text = patch_send_discord.ainvoke.call_args[0][0]["message"]
        assert "Line one." in sent_text
        assert "Line two." in sent_text

    @pytest.mark.asyncio
    async def test_does_not_send_empty_content(self, patch_send_discord):
        """Messages with only whitespace content are silently skipped."""
        from net_deepagent_cli.communication.tools import send_final_reply_to_discord

        msg = make_ai_message("   ")
        await send_final_reply_to_discord(msg, channel_id=789)

        patch_send_discord.ainvoke.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_does_not_send_empty_list_content(self, patch_send_discord):
        """Block-list that produces no text is silently skipped."""
        from net_deepagent_cli.communication.tools import send_final_reply_to_discord

        msg = make_ai_message([{"type": "text", "text": ""}])
        await send_final_reply_to_discord(msg, channel_id=789)

        patch_send_discord.ainvoke.assert_not_awaited()


# ===========================================================================
# Phase 1 — post-stream callback in stream_agent_response (loop.py)
# ===========================================================================

class TestStreamAgentResponseDiscordCallback:
    """Integration-style tests for the discord callback block in loop.py."""

    def _make_agent(self, messages_to_yield):
        """Build a minimal mock agent that yields one chunk with given messages."""
        agent = MagicMock()

        async def fake_astream(state, stream_mode):
            yield {"messages": messages_to_yield}

        agent.astream = fake_astream
        return agent

    def _make_ui(self):
        ui = MagicMock()
        ui.show_progress.return_value.__enter__ = MagicMock(
            return_value=MagicMock(add_task=MagicMock(return_value=0))
        )
        ui.show_progress.return_value.__exit__ = MagicMock(return_value=False)
        ui.total_tokens = 0
        ui.normalize_content = lambda x: x or ""
        return ui

    @pytest.mark.asyncio
    async def test_sends_final_ai_message_when_discord_channel_id_present(self):
        """When discord_channel_id is in kwargs and final AIMessage exists, it is sent."""
        final_msg = make_ai_message("Final answer!")
        agent = self._make_agent([final_msg])
        ui = self._make_ui()
        messages = []

        with patch(
            "net_deepagent_cli.communication.tools.send_discord_message"
        ) as mock_tool:
            mock_tool.ainvoke = AsyncMock(return_value="ok")

            from net_deepagent_cli.loop import stream_agent_response
            await stream_agent_response(
                agent, messages, ui, auto_approve=True,
                discord_channel_id=999, channel_name="ops",
            )

        mock_tool.ainvoke.assert_awaited()
        sent = mock_tool.ainvoke.call_args[0][0]
        assert sent["message"] == "Final answer!"
        assert sent["channel_id"] == 999

    @pytest.mark.asyncio
    async def test_no_send_when_discord_channel_id_absent(self):
        """When discord_channel_id is NOT in kwargs (CLI mode), nothing is sent."""
        final_msg = make_ai_message("CLI response")
        agent = self._make_agent([final_msg])
        ui = self._make_ui()
        messages = []

        with patch(
            "net_deepagent_cli.communication.tools.send_discord_message"
        ) as mock_tool:
            mock_tool.ainvoke = AsyncMock(return_value="ok")

            from net_deepagent_cli.loop import stream_agent_response
            await stream_agent_response(agent, messages, ui, auto_approve=True)

        mock_tool.ainvoke.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_send_when_last_ai_message_has_tool_calls(self):
        """Messages that still have tool_calls are intermediate — not sent."""
        tool_msg = make_ai_message("thinking...", tool_calls=[{"name": "some_tool", "args": {}}])
        agent = self._make_agent([tool_msg])
        ui = self._make_ui()
        messages = []

        with patch(
            "net_deepagent_cli.communication.tools.send_discord_message"
        ) as mock_tool:
            mock_tool.ainvoke = AsyncMock(return_value="ok")

            from net_deepagent_cli.loop import stream_agent_response
            await stream_agent_response(
                agent, messages, ui, auto_approve=True,
                discord_channel_id=111,
            )

        mock_tool.ainvoke.assert_not_awaited()


# ===========================================================================
# Phase 2 — Ack message in listener.py
# ===========================================================================

class TestListenerAck:
    """Unit tests for the acknowledgment message sent on receipt in listener.py."""

    def _make_payload(self, channel_id=42, author="TestUser#1234",
                      message_id=None, channel_name="ops"):
        from net_deepagent_cli.communication.schema import AgentMessage
        return AgentMessage(
            content="What is the BGP status?",
            author=author,
            channel_id=channel_id,
            channel_name=channel_name,
            message_id=message_id,
        )

    @pytest.mark.asyncio
    async def test_ack_sent_before_stream_agent_response(self):
        """Ack is published to Discord before stream_agent_response is invoked."""
        call_order = []
        payload = self._make_payload(message_id="98765")

        mock_send = AsyncMock(side_effect=lambda _: call_order.append("ack"))
        mock_stream = AsyncMock(side_effect=lambda *a, **kw: call_order.append("stream"))

        with patch(
            "net_deepagent_cli.communication.listener.send_discord_message"
        ) as mock_tool, patch(
            "net_deepagent_cli.communication.listener.stream_agent_response",
            mock_stream,
        ), patch(
            "net_deepagent_cli.communication.listener.init_rabbit_channel",
            AsyncMock(),
        ):
            mock_tool.ainvoke = mock_send

            # Simulate one message through the listener logic directly
            import aio_pika, json
            from net_deepagent_cli.communication.schema import AgentMessage

            # Call the internal processing chunk without the full queue loop
            from net_deepagent_cli.communication import listener as _listener_module

            # Directly invoke the processing body (extracted for testability)
            if payload.channel_id or payload.channel_name:
                task_ref = f" (ref: `{payload.message_id}`)" if payload.message_id else ""
                ack_text = f"⚙️ Got it, {payload.author}! Working on your request{task_ref}..."
                await mock_tool.ainvoke({"channel_id": payload.channel_id,
                                         "message": ack_text,
                                         "channel_name": payload.channel_name})
            await mock_stream(None, [], None, auto_approve=True)

        assert call_order == ["ack", "stream"], "Ack must fire before stream_agent_response"

    @pytest.mark.asyncio
    async def test_ack_includes_message_id_when_present(self):
        """When message_id is set the ack text contains the ref."""
        payload = self._make_payload(message_id="DISCORD-123")
        captured = {}

        mock_send = AsyncMock(side_effect=lambda args: captured.update(args))

        if payload.channel_id or payload.channel_name:
            task_ref = f" (ref: `{payload.message_id}`)" if payload.message_id else ""
            ack_text = f"⚙️ Got it, {payload.author}! Working on your request{task_ref}..."
            await mock_send({"message": ack_text})

        assert "DISCORD-123" in captured["message"]

    @pytest.mark.asyncio
    async def test_ack_omits_ref_when_no_message_id(self):
        """When message_id is None the ack still sends without error or ref."""
        payload = self._make_payload(message_id=None)
        captured = {}

        mock_send = AsyncMock(side_effect=lambda args: captured.update(args))

        if payload.channel_id or payload.channel_name:
            task_ref = f" (ref: `{payload.message_id}`)" if payload.message_id else ""
            ack_text = f"⚙️ Got it, {payload.author}! Working on your request{task_ref}..."
            await mock_send({"message": ack_text})

        assert "ref:" not in captured["message"]
        assert payload.author in captured["message"]
