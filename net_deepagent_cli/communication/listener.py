import asyncio
import aio_pika
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from net_deepagent_cli.communication.schema import AgentMessage
from net_deepagent_cli.communication.tools import init_rabbit_channel
from net_deepagent_cli.communication.logger import comm_logger as logger
from net_deepagent_cli.loop import stream_agent_response

async def run_agent_listener(agent: Any, connection: aio_pika.Connection, ui: Any = None):
    """
    Consumer loop that picks up messages from inbound.agent and invokes the agent.
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

                # Build initial message list
                msg = HumanMessage(content=payload.content)
                messages_list = [msg]
                
                await stream_agent_response(
                    agent, 
                    messages_list, 
                    ui, 
                    auto_approve=True,
                    discord_channel_id=payload.channel_id,
                    author=payload.author,
                    channel_name=payload.channel_name
                )

                # NEW: Automatically send the final AIMessage back to Discord if it has content
                # and if the agent didn't already send a discord message via tool (optional check?)
                # For now, let's just send the final response as it's common practice.
                if messages_list and isinstance(messages_list[-1], AIMessage):
                    final_msg = messages_list[-1]
                    if final_msg.content:
                        from net_deepagent_cli.communication.tools import send_discord_message
                        logger.info(f"Automatically sending final response to Discord: {final_msg.content[:50]}...")
                        await send_discord_message.ainvoke({
                            "channel_id": payload.channel_id,
                            "message": final_msg.content,
                            "channel_name": payload.channel_name
                        })
            except Exception as e:
                logger.error(f"Error processing agent job: {e}", exc_info=True)
