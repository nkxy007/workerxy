import aio_pika
import json
import creds
import logging
from langchain_core.tools import tool
from langchain_core.messages import AIMessage
from net_deepagent_cli.communication.schema import AgentMessage
from typing import Optional, Union

logger = logging.getLogger(__name__)

_rabbit_channel = None

async def init_rabbit_channel(connection: aio_pika.Connection):
    """Initialize RabbitMQ channels and declare queues on the agent side."""
    global _rabbit_channel
    _rabbit_channel = await connection.channel()
    await _rabbit_channel.declare_queue("outbound.agent", durable=True)
    await _rabbit_channel.declare_queue("inbound.agent", durable=True)

@tool
async def send_chat_message(channel_id: Optional[Union[int, str]] = None, message: str = "", channel_name: Optional[str] = None) -> str:
    """
    Send a message to a Chat channel (Discord/Slack). 
    You can specify either channel_id (preferred) or channel_name (e.g., 'Network-jobs').
    """
    if _rabbit_channel is None:
        return "Error: RabbitMQ channel not initialized on agent."

    payload = AgentMessage(
        content=message,
        author="agent",
        channel_id=channel_id,
        channel_name=channel_name
    )

    try:
        await _rabbit_channel.default_exchange.publish(
            aio_pika.Message(
                body=payload.to_json(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key="outbound.agent",
        )
        return f"Reply sent to Discord channel {channel_id} via RabbitMQ."
    except Exception as e:
        return f"Error publishing reply to RabbitMQ: {e}"


async def send_final_reply_to_chat(
    message: AIMessage,
    channel_id: Optional[int],
    channel_name: Optional[str] = None,
) -> None:
    """
    Extract plain text from a final AIMessage and publish it to outbound.agent.

    Handles both string content and block-list content (e.g. Anthropic-style
    [{"type": "text", "text": "..."}]). Silently skips empty messages.
    Called by stream_agent_response in loop.py (Phase 1 — headless auto-reply).
    """
    content = message.content

    # Flatten block-list format
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        content = "\n".join(parts)

    if not isinstance(content, str):
        content = str(content)

    content = content.strip()
    if not content:
        logger.debug("send_final_reply_to_chat: empty content, skipping.")
        return

    logger.info(f"Sending final AI reply to Chat channel {channel_id or channel_name!r}...")
    result = await send_chat_message.ainvoke({
        "channel_id": channel_id,
        "message": content,
        "channel_name": channel_name,
    })
    
    if isinstance(result, str) and result.startswith("Error"):
        logger.error(f"send_final_reply_to_chat failed: {result}")
    else:
        logger.info(f"send_final_reply_to_chat success: {result}")
