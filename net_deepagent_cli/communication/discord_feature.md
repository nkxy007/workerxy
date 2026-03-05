# Discord Integration Plan — LangGraph Agent + RabbitMQ

## Overview

Add bidirectional Discord communication to the existing LangGraph CLI agent using **RabbitMQ as the message broker**. The Discord bot and the LangGraph agent are **fully decoupled, independent processes** that communicate only through RabbitMQ queues. This architecture is designed for enterprise-grade network operations where resilience, auditability, and extensibility across multiple interfaces (Discord, Slack, alerting systems) are required.

---

## Architecture Diagram

```
                        ┌─────────────────────────────┐
                        │        RabbitMQ Broker       │
                        │     (CentOS Stream server)   │
                        │                              │
                        │  ┌──────────────────────┐   │
  Discord User          │  │ Queue: inbound.agent  │   │
      │                 │  │  (Discord → Agent)    │   │
      ▼                 │  └──────────────────────┘   │
┌───────────────┐       │  ┌──────────────────────┐   │
│  Discord Bot  │◀─────▶│  │ Queue: outbound.agent │   │
│  (standalone) │       │  │  (Agent → Discord)    │   │
└───────────────┘       │  └──────────────────────┘   │
                        │  ┌──────────────────────┐   │
                        │  │ Queue: events.network │   │
                        │  │ (Alerts / Monitoring) │   │
                        │  └──────────────────────┘   │
                        └──────────────┬──────────────┘
                                       │
                                       ▼
                        ┌─────────────────────────────┐
                        │     LangGraph Agent          │
                        │                              │
                        │  - Consumes inbound.agent    │
                        │  - Publishes outbound.agent  │
                        │  - Tool calls (SSH, CLI APIs)│
                        └─────────────────────────────┘
```

---

## Architecture Decision Summary

| Concern | Decision | Rationale |
|---|---|---|
| Message broker | RabbitMQ on CentOS Stream | Enterprise-grade, persistent, supports routing and dead-letter queues |
| Receiving messages (agent side) | Consume from `inbound.agent` queue | Agent subscribes independently; broker buffers if agent is busy or restarting |
| Sending messages (agent side) | Publish to `outbound.agent` queue as a LangGraph tool call | Keeps sending explicit and agent-controlled |
| Discord bot | Standalone process | Fully decoupled; can be restarted independently of the agent |
| Python async client | `aio-pika` | Native async, fits LangGraph and discord.py event loops |
| Message format | JSON over AMQP | Human-readable, easy to log and audit |

---

## RabbitMQ Setup (CentOS Stream)

### Install

```bash
# Add Erlang and RabbitMQ repos
sudo rpm --import 'https://github.com/rabbitmq/signing-keys/releases/download/3.0/rabbitmq-release-signing-key.asc'
sudo rpm --import 'https://github.com/rabbitmq/signing-keys/releases/download/3.0/cloudsmith.rabbitmq-erlang.E495BB49CC4BBE5B.key'
sudo rpm --import 'https://github.com/rabbitmq/signing-keys/releases/download/3.0/cloudsmith.rabbitmq-server.9F4587F226208342.key'

#Create repos manually 
sudo tee /etc/yum.repos.d/rabbitmq.repo <<EOF
[modern-erlang]
name=modern-erlang-el9
baseurl=https://yum1.novemberain.com/erlang/el/9/\$basearch
repo_gpgcheck=1
enabled=1
gpgkey=https://github.com/rabbitmq/signing-keys/releases/download/3.0/cloudsmith.rabbitmq-erlang.E495BB49CC4BBE5B.key
gpgcheck=1
sslverify=1
sslcacert=/etc/pki/tls/certs/ca-bundle.crt
metadata_expire=300
pkg_gpgcheck=1
autorefresh=1
type=rpm-md

[modern-erlang-noarch]
name=modern-erlang-el9-noarch
baseurl=https://yum1.novemberain.com/erlang/el/9/noarch
repo_gpgcheck=1
enabled=1
gpgkey=https://github.com/rabbitmq/signing-keys/releases/download/3.0/cloudsmith.rabbitmq-erlang.E495BB49CC4BBE5B.key
gpgcheck=1
sslverify=1
sslcacert=/etc/pki/tls/certs/ca-bundle.crt
metadata_expire=300
pkg_gpgcheck=1
autorefresh=1
type=rpm-md

[rabbitmq-el9]
name=rabbitmq-el9
baseurl=https://yum1.novemberain.com/rabbitmq/el/9/\$basearch
repo_gpgcheck=1
enabled=1
gpgkey=https://github.com/rabbitmq/signing-keys/releases/download/3.0/cloudsmith.rabbitmq-server.9F4587F226208342.key
       https://github.com/rabbitmq/signing-keys/releases/download/3.0/rabbitmq-release-signing-key.asc
gpgcheck=1
sslverify=1
sslcacert=/etc/pki/tls/certs/ca-bundle.crt
metadata_expire=300
pkg_gpgcheck=1
autorefresh=1
type=rpm-md

[rabbitmq-el9-noarch]
name=rabbitmq-el9-noarch
baseurl=https://yum1.novemberain.com/rabbitmq/el/9/noarch
repo_gpgcheck=1
enabled=1
gpgkey=https://github.com/rabbitmq/signing-keys/releases/download/3.0/cloudsmith.rabbitmq-server.9F4587F226208342.key
       https://github.com/rabbitmq/signing-keys/releases/download/3.0/rabbitmq-release-signing-key.asc
gpgcheck=1
sslverify=1
sslcacert=/etc/pki/tls/certs/ca-bundle.crt
metadata_expire=300
pkg_gpgcheck=1
autorefresh=1
type=rpm-md
EOF
# Install
sudo dnf install -y erlang rabbitmq-server

# Start and enable on boot
sudo systemctl start rabbitmq-server
sudo systemctl enable rabbitmq-server

# Enable management UI (http://your-server:15672)
sudo rabbitmq-plugins enable rabbitmq_management

# Create a dedicated user (do not use guest in production)
sudo rabbitmqctl add_user agent_user yourpassword
sudo rabbitmqctl set_user_tags agent_user administrator
sudo rabbitmqctl set_permissions -p / agent_user ".*" ".*" ".*"

# Open firewall ports
sudo firewall-cmd --permanent --add-port=5672/tcp   # AMQP
sudo firewall-cmd --permanent --add-port=15672/tcp  # Management UI
sudo firewall-cmd --reload
```

### Queue Topology

| Queue | Producer | Consumer | Purpose |
|---|---|---|---|
| `inbound.agent` | Discord Bot | LangGraph Agent | User messages from Discord to agent |
| `outbound.agent` | LangGraph Agent | Discord Bot | Agent replies back to Discord |
| `events.network` | Monitoring tools | LangGraph Agent | Alerts and network events (future) |

---

## New Dependencies

```
aio-pika>=9.0.0       # async RabbitMQ client
discord.py>=2.3.0     # Discord Gateway WebSocket
python-dotenv         # environment variable management
```

---

## Environment Variables

```bash
# .env
DISCORD_BOT_TOKEN=your_discord_bot_token
RABBITMQ_URL=amqp://agent_user:yourpassword@your-server-ip:5672/
```

---

## Step-by-Step Implementation

### Step 1 — Shared Message Schema

Define a consistent JSON schema for all messages travelling through the broker. Both the Discord bot and the agent must serialize/deserialize using this schema.

**File: `shared/schema.py`**
```python
from dataclasses import dataclass, asdict
from typing import Optional
import json

@dataclass
class AgentMessage:
    content: str          # the text of the message
    author: str           # who sent it
    channel_id: int       # Discord channel to reply to
    guild_id: Optional[int] = None
    message_id: Optional[str] = None  # for correlation/auditing

    def to_json(self) -> bytes:
        return json.dumps(asdict(self)).encode()

    @classmethod
    def from_json(cls, data: bytes) -> "AgentMessage":
        return cls(**json.loads(data))
```

---

### Step 2 — Discord Bot (Standalone Process)

The Discord bot is its own process. It does two things only:
- **Receive** messages from Discord → publish to `inbound.agent`
- **Consume** from `outbound.agent` → send to Discord channel

**File: `discord_bot/bot.py`**
```python
import asyncio
import os
import discord
import aio_pika
from shared.schema import AgentMessage
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

class AgentBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rabbit_connection = None
        self.inbound_channel = None

    async def setup_hook(self):
        # Connect to RabbitMQ when bot starts
        self.rabbit_connection = await aio_pika.connect_robust(
            os.environ["RABBITMQ_URL"]
        )
        self.inbound_channel = await self.rabbit_connection.channel()

        # Start consuming outbound replies from agent
        asyncio.create_task(self.consume_outbound())

    async def on_ready(self):
        print(f"Discord bot online as {self.user}")

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # Only respond to @mentions (recommended for enterprise)
        if self.user not in message.mentions:
            return

        payload = AgentMessage(
            content=message.content,
            author=str(message.author),
            channel_id=message.channel.id,
            guild_id=message.guild.id if message.guild else None,
        )

        # Publish to inbound.agent queue
        await self.inbound_channel.default_exchange.publish(
            aio_pika.Message(
                body=payload.to_json(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key="inbound.agent",
        )
        print(f"Queued message from {message.author}")

    async def consume_outbound(self):
        # Consume replies from the agent and send to Discord
        channel = await self.rabbit_connection.channel()
        queue = await channel.declare_queue("outbound.agent", durable=True)

        async for message in queue:
            async with message.process():
                payload = AgentMessage.from_json(message.body)
                discord_channel = self.get_channel(payload.channel_id)
                if discord_channel:
                    await discord_channel.send(payload.content)

bot = AgentBot(intents=intents)

if __name__ == "__main__":
    bot.run(os.environ["DISCORD_BOT_TOKEN"])
```

---

### Step 3 — Send Message Tool (Agent Side)

The agent publishes to `outbound.agent` via a LangGraph tool call.

**File: `agent/tools/discord_tools.py`**
```python
import os
import aio_pika
from langchain_core.tools import tool
from shared.schema import AgentMessage

_rabbit_channel = None

async def init_rabbit_channel(connection: aio_pika.Connection):
    global _rabbit_channel
    _rabbit_channel = await connection.channel()
    await _rabbit_channel.declare_queue("outbound.agent", durable=True)
    await _rabbit_channel.declare_queue("inbound.agent", durable=True)

@tool
async def send_discord_message(channel_id: int, message: str) -> str:
    """Send a message to a Discord channel. Use this to reply to the user."""
    payload = AgentMessage(
        content=message,
        author="agent",
        channel_id=channel_id,
    )
    await _rabbit_channel.default_exchange.publish(
        aio_pika.Message(
            body=payload.to_json(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        ),
        routing_key="outbound.agent",
    )
    return f"Reply sent to channel {channel_id}."
```

---

### Step 4 — Agent Listener (Consume from inbound.agent)

The agent runs its own consumer loop, picking up messages from `inbound.agent` and invoking the LangGraph graph.

**File: `agent/listener.py`**
```python
import asyncio
import os
import aio_pika
from shared.schema import AgentMessage
from agent.tools.discord_tools import init_rabbit_channel

async def run_agent_listener(graph, connection: aio_pika.Connection):
    await init_rabbit_channel(connection)

    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)  # process one at a time
    queue = await channel.declare_queue("inbound.agent", durable=True)

    print("Agent listener started. Waiting for messages...")

    async for message in queue:
        async with message.process():
            payload = AgentMessage.from_json(message.body)
            print(f"Processing message from {payload.author}: {payload.content}")

            state = {
                "messages": [{"role": "user", "content": payload.content}],
                "discord_channel_id": payload.channel_id,
                "author": payload.author,
            }

            try:
                await graph.ainvoke(state)
            except Exception as e:
                print(f"Agent error: {e}")
```

---

### Step 5 — Agent Entrypoint

**File: `agent/main.py`**
```python
import asyncio
import os
import aio_pika
from dotenv import load_dotenv
from agent.graph import build_graph
from agent.listener import run_agent_listener

load_dotenv()

async def main():
    connection = await aio_pika.connect_robust(os.environ["RABBITMQ_URL"])
    graph = build_graph()
    await run_agent_listener(graph, connection)

if __name__ == "__main__":
    asyncio.run(main())
```

---

### Step 6 — LangGraph State Schema

Add `discord_channel_id` to your state so it flows through to the tool call:

```python
from typing import Optional
from langgraph.graph import MessagesState

class AgentState(MessagesState):
    discord_channel_id: Optional[int] = None
    author: Optional[str] = None
```

---

## Final File Structure

```
project/
├── shared/
│   └── schema.py                  ← AgentMessage dataclass (shared by both processes)
│
├── discord_bot/
│   ├── bot.py                     ← standalone Discord bot process
│   └── requirements.txt           ← discord.py, aio-pika, python-dotenv
│
├── agent/
│   ├── main.py                    ← agent entrypoint (connects to RabbitMQ, starts listener)
│   ├── graph.py                   ← existing LangGraph graph (add send_discord_message tool)
│   ├── state.py                   ← add discord_channel_id to AgentState
│   ├── listener.py                ← consumes inbound.agent queue
│   └── tools/
│       ├── existing_tools.py      ← your existing tools (unchanged)
│       └── discord_tools.py       ← send_discord_message tool
│
├── main_cli.py                    ← existing CLI entrypoint (unchanged)
└── .env                           ← DISCORD_BOT_TOKEN, RABBITMQ_URL
```

---

## Running the System

Each process runs independently:

```bash
# Terminal 1 — RabbitMQ runs as a system service
sudo systemctl start rabbitmq-server

# Terminal 2 — Start the Discord bot
python discord_bot/bot.py

# Terminal 3 — Start the LangGraph agent
python agent/main.py
```

You can restart either the bot or the agent independently. Messages published while the agent is down are held in the `inbound.agent` queue and delivered when it comes back up.

---

## How a Message Flows End-to-End

```
1. User mentions @bot in Discord channel
2. discord_bot/bot.py → on_message() fires
3. Bot publishes AgentMessage JSON to RabbitMQ: inbound.agent
4. agent/listener.py consumes the message
5. LangGraph graph.ainvoke(state) runs
6. Agent decides to reply → calls send_discord_message tool
7. Tool publishes AgentMessage JSON to RabbitMQ: outbound.agent
8. discord_bot/bot.py → consume_outbound() picks it up
9. Bot sends reply to the original Discord channel
10. User sees the response
```

---

## Edge Cases & Considerations

| Scenario | Handling |
|---|---|
| Agent crashes mid-processing | `durable=True` queues + `PERSISTENT` messages survive broker restart; `prefetch_count=1` ensures unacked message is requeued |
| Discord bot restarts | Agent keeps publishing to `outbound.agent`; bot drains the queue on reconnect |
| Multiple users messaging simultaneously | Messages queue up and are processed serially by default. Increase `prefetch_count` and spawn tasks for concurrency |
| Message too long for Discord | Discord has a 2000-char limit; add chunking in the `consume_outbound` method of the bot |
| Sensitive network commands | Route high-risk tool calls to a separate `approval.required` queue; a human confirms via Discord before execution |
| Audit trail | All messages pass through RabbitMQ; enable message persistence and add a logging consumer for a full audit log |

---

## Future Extensions (Beyond POC)

- **Slack bot** — add a second standalone bot consuming from the same `outbound.agent` queue and publishing to `inbound.agent`. The agent code is untouched.
- **Monitoring alerts** — Prometheus/Zabbix publishes to `events.network`; agent subscribes and auto-responds to incidents
- **Human-in-the-loop approval** — high-risk actions routed to an `approval.required` queue; Discord bot presents a confirm/deny button to the operator
- **Multiple agents** — a triage agent, remediation agent, and reporting agent each subscribe to different topics independently
- **Kafka migration** — when you outgrow RabbitMQ, the queue interface is already abstracted enough to swap brokers with minimal agent-side changes