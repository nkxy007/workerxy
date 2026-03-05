import aio_pika
import json
import creds
from langchain_core.tools import tool
from net_deepagent_cli.communication.schema import AgentMessage
from typing import Optional

_rabbit_channel = None

async def init_rabbit_channel(connection: aio_pika.Connection):
    """Initialize RabbitMQ channels and declare queues on the agent side."""
    global _rabbit_channel
    _rabbit_channel = await connection.channel()
    await _rabbit_channel.declare_queue("outbound.agent", durable=True)
    await _rabbit_channel.declare_queue("inbound.agent", durable=True)

@tool
async def send_discord_message(channel_id: Optional[int] = None, message: str = "", channel_name: Optional[str] = None) -> str:
    """
    Send a message to a Discord channel. 
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
