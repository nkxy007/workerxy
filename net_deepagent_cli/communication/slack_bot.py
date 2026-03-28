import asyncio
import os
import sys
import logging
from pathlib import Path
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
import aio_pika

# Add project root to path to import creds and logic
sys.path.append(str(Path(__file__).parent.parent.parent))

import creds
from net_deepagent_cli.communication.schema import AgentMessage
from net_deepagent_cli.communication.logger import setup_logger

logger = setup_logger("slack_bot")

# Assuming user puts SLACK_BOT_AUTH_TOKEN and SLACK_BOT_SOCKET_TOKEN in creds or env
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_AUTH_TOKEN") or getattr(creds, "SLACK_BOT_AUTH_TOKEN", None)
SLACK_APP_TOKEN = os.environ.get("SLACK_BOT_SOCKET_TOKEN") or getattr(creds, "SLACK_BOT_SOCKET_TOKEN", None)

app = AsyncApp(token=SLACK_BOT_TOKEN)

class AgentSlackBot:
    def __init__(self, app: AsyncApp):
        self.app = app
        self.rabbit_connection = None
        self.inbound_channel = None
        self.rabbitmq_url = f"amqp://{creds.RABBITMQUSER}:{creds.RABBITMQ_PASSWORD}@localhost:5672/"

    async def setup_hook(self):
        logger.info(f"Connecting to RabbitMQ at {self.rabbitmq_url}...")
        try:
            self.rabbit_connection = await aio_pika.connect_robust(self.rabbitmq_url)
            self.inbound_channel = await self.rabbit_connection.channel()
            
            await self.inbound_channel.declare_queue("inbound.agent", durable=True)
            await self.inbound_channel.declare_queue("outbound.agent", durable=True)
            
            asyncio.create_task(self.consume_outbound())
            logger.info("RabbitMQ connection established and outbound consumer started.")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            sys.exit(1)

    async def consume_outbound(self):
        try:
            channel = await self.rabbit_connection.channel()
            queue = await channel.declare_queue("outbound.agent", durable=True)

            async for message in queue:
                async with message.process():
                    payload = AgentMessage.from_json(message.body)
                    logger.info(f"Processing outbound message for channel_id={payload.channel_id} name={payload.channel_name}")
                    
                    slack_channel = payload.channel_id
                    
                    if not slack_channel and payload.channel_name:
                        # In Slack, channel names aren't as easily translatable to IDs without an API call
                        # that iterates through public channels. For simplicity, we assume channel_id is provided.
                        # If a name is passed, we can try to send it if Slack allows it (sometimes it does for #channel)
                        slack_channel = f"#{payload.channel_name}"
                        
                    if slack_channel:
                        content = payload.content
                        max_length = 4000 # Slack's actual limit is ~4000
                        
                        if len(content) <= max_length:
                            await self.app.client.chat_postMessage(channel=slack_channel, text=content)
                        else:
                            # Split into chunks
                            lines = content.split('\n')
                            current_chunk = ""
                            for line in lines:
                                if len(current_chunk) + len(line) + 1 <= max_length:
                                    current_chunk += line + '\n'
                                else:
                                    if current_chunk.strip():
                                        await self.app.client.chat_postMessage(channel=slack_channel, text=current_chunk)
                                        current_chunk = ""
                                        
                                    if len(line) > max_length:
                                        for i in range(0, len(line), max_length):
                                            await self.app.client.chat_postMessage(channel=slack_channel, text=line[i:i+max_length])
                                    else:
                                        current_chunk = line + '\n'
                                        
                            if current_chunk.strip():
                                await self.app.client.chat_postMessage(channel=slack_channel, text=current_chunk)
                    else:
                        logger.error(f"Error: Could not find channel {payload.channel_id or payload.channel_name}")
        except Exception as e:
            logger.error(f"Error in consume_outbound: {e}")


# Slack Bolt Event Listeners
@app.event("app_mention")
async def handle_app_mention(event, say):
    # This runs when somebody mentions the bot in a channel
    user_id = event["user"]
    text = event["text"]
    channel_id = event["channel"]
    ts = event["ts"]
    
    logger.info(f"Received app_mention from {user_id}: {text}")
    
    payload = AgentMessage(
        content=text,
        author=user_id,
        channel_id=channel_id,
        guild_id=event.get("team"),
        message_id=ts,
    )
    
    try:
        if bot_instance and bot_instance.inbound_channel:
            await bot_instance.inbound_channel.default_exchange.publish(
                aio_pika.Message(
                    body=payload.to_json(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                ),
                routing_key="inbound.agent",
            )
            logger.info(f"Queued message from {user_id} to inbound.agent")
    except Exception as e:
        logger.error(f"Error publishing to RabbitMQ: {e}")

@app.event("message")
async def handle_message_events(event):
    # This runs for direct messages (if DMs are subscribed)
    # Ignore bot messages
    if "bot_id" in event:
        return
        
    channel_type = event.get("channel_type")
    if channel_type != "im":
        # Only handle direct messages here, app_mentions covers channel mentions
        return
        
    user_id = event["user"]
    text = event["text"]
    channel_id = event["channel"]
    ts = event["ts"]
    
    logger.info(f"Received direct message from {user_id}: {text}")
    
    payload = AgentMessage(
        content=text,
        author=user_id,
        channel_id=channel_id,
        guild_id=event.get("team"),
        message_id=ts,
    )
    
    try:
        if bot_instance and bot_instance.inbound_channel:
            await bot_instance.inbound_channel.default_exchange.publish(
                aio_pika.Message(
                    body=payload.to_json(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                ),
                routing_key="inbound.agent",
            )
            logger.info(f"Queued DM from {user_id} to inbound.agent")
    except Exception as e:
        logger.error(f"Error publishing to RabbitMQ: {e}")

bot_instance = None

async def main_async(args):
    global bot_instance
    
    from net_deepagent_cli.communication.logger import set_log_level
    set_log_level(args.log_level)
    
    if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
        logger.error("Missing SLACK_BOT_AUTH_TOKEN or SLACK_BOT_SOCKET_TOKEN in creds.py or env.")
        sys.exit(1)
        
    bot_instance = AgentSlackBot(app)
    await bot_instance.setup_hook()
    
    handler = AsyncSocketModeHandler(app, SLACK_APP_TOKEN)
    logger.info("Starting Slack bot in Socket Mode...")
    await handler.start_async()

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Slack Bot for Net DeepAgent")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], help="Set the logging level")
    
    args = parser.parse_args()
    
    asyncio.run(main_async(args))

if __name__ == "__main__":
    main()
