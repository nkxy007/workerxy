import asyncio
import os
import discord
import aio_pika
import sys
import logging
from pathlib import Path

# Add project root to path to import creds and logic
sys.path.append(str(Path(__file__).parent.parent.parent))

import creds
from net_deepagent_cli.communication.schema import AgentMessage
from net_deepagent_cli.communication.logger import comm_logger as logger

# Suppress noisy discord logs
logging.getLogger('discord').setLevel(logging.WARNING)
logging.getLogger('aiormq').setLevel(logging.WARNING)

# Intents
intents = discord.Intents.default()
intents.message_content = True

class AgentBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rabbit_connection = None
        self.inbound_channel = None
        self.rabbitmq_url = f"amqp://{creds.RABBITMQUSER}:{creds.RABBITMQ_PASSWORD}@localhost:5672/"

    async def setup_hook(self):
        # Connect to RabbitMQ when bot starts
        logger.info(f"Connecting to RabbitMQ at {self.rabbitmq_url}...")
        try:
            self.rabbit_connection = await aio_pika.connect_robust(self.rabbitmq_url)
            self.inbound_channel = await self.rabbit_connection.channel()
            # Declare queues
            await self.inbound_channel.declare_queue("inbound.agent", durable=True)
            await self.inbound_channel.declare_queue("outbound.agent", durable=True)
            
            # Start consuming outbound replies from agent
            asyncio.create_task(self.consume_outbound())
            logger.info("RabbitMQ connection established and outbound consumer started.")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            sys.exit(1)

    async def on_ready(self):
        logger.info(f"Discord bot online as {self.user}")

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # Only respond to @mentions (as per enterprise recommendation in plan)
        if self.user not in message.mentions:
            return

        logger.info(f"Received message from {message.author}: {message.content}")

        payload = AgentMessage(
            content=message.content,
            author=str(message.author),
            channel_id=message.channel.id,
            guild_id=message.guild.id if message.guild else None,
        )

        # Publish to inbound.agent queue
        try:
            await self.inbound_channel.default_exchange.publish(
                aio_pika.Message(
                    body=payload.to_json(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                ),
                routing_key="inbound.agent",
            )
            logger.info(f"Queued message from {message.author} to inbound.agent")
        except Exception as e:
            logger.error(f"Error publishing to RabbitMQ: {e}")

    async def consume_outbound(self):
        # Consume replies from the agent and send to Discord
        try:
            channel = await self.rabbit_connection.channel()
            queue = await channel.declare_queue("outbound.agent", durable=True)

            async for message in queue:
                async with message.process():
                    payload = AgentMessage.from_json(message.body)
                    logger.info(f"Processing outbound message for channel_id={payload.channel_id} name={payload.channel_name}")
                    
                    discord_channel = None
                    if payload.channel_id:
                        discord_channel = self.get_channel(payload.channel_id)
                    
                    if not discord_channel and payload.channel_name:
                        # Try to find channel by name
                        for guild in self.guilds:
                            discord_channel = discord.utils.get(guild.channels, name=payload.channel_name)
                            if discord_channel:
                                break
                    
                    if discord_channel:
                        await discord_channel.send(payload.content)
                    else:
                        logger.error(f"Error: Could not find channel {payload.channel_id or payload.channel_name}")
        except Exception as e:
            logger.error(f"Error in consume_outbound: {e}")

def main():
    bot = AgentBot(intents=intents)
    try:
        bot.run(creds.DISCORD_API_KEY)
    except Exception as e:
        logger.error(f"Error running Discord bot: {e}")

if __name__ == "__main__":
    main()
