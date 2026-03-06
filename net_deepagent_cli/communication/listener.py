import asyncio
import aio_pika
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from net_deepagent_cli.communication.schema import AgentMessage
from net_deepagent_cli.communication.tools import init_rabbit_channel, send_discord_message
from net_deepagent_cli.communication.logger import comm_logger as logger
from net_deepagent_cli.loop import stream_agent_response

async def run_agent_listener(agent: Any, connection: aio_pika.Connection, ui: Any = None):
    """
    Consumer loop that picks up messages from inbound.agent and invokes the agent.

    For each inbound message:
      - Phase 2: Immediately sends an ack to Discord so the user knows work has started.
      - Phase 1: stream_agent_response handles sending the final AI reply once done.
    """
    # Initialize the publishing channel for tools too
    await init_rabbit_channel(connection)

    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)  # process one at a time
    queue = await channel.declare_queue("inbound.agent", durable=True)

    logger.info("Agent listener online. Waiting for messages in inbound.agent...")

    async for message in queue:
        async with message.process():
            try:
                payload = AgentMessage.from_json(message.body)
                logger.info(f"Processing message from {payload.author}: {payload.content}")

                # --- Phase 2: Acknowledge receipt immediately ---
                if payload.channel_id or payload.channel_name:
                    task_ref = f" (ref: `{payload.message_id}`)" if payload.message_id else ""
                    ack_text = f"⚙️ Got it, {payload.author}! Working on your request{task_ref}..."
                    await send_discord_message.ainvoke({
                        "channel_id": payload.channel_id,
                        "message": ack_text,
                        "channel_name": payload.channel_name,
                    })
                    logger.info("Phase 2: Ack sent to Discord.")

                # Build initial message list
                msg = HumanMessage(content=payload.content)
                messages_list = [msg]

                # stream_agent_response handles Phase 1 (final reply to Discord)
                # by detecting discord_channel_id in kwargs after streaming completes.
                await stream_agent_response(
                    agent,
                    messages_list,
                    ui,
                    auto_approve=True,
                    discord_channel_id=payload.channel_id,
                    author=payload.author,
                    channel_name=payload.channel_name,
                )

            except Exception as e:
                logger.error(f"Error processing agent job: {e}", exc_info=True)
