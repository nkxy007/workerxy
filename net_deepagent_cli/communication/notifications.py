import os
import aiohttp
from typing import Optional, Any
import creds

async def dispatch_permission_webhook(
    agent_name: str,
    tool_name: str,
    args_json: str,
    logger: Optional[Any] = None
) -> None:
    """
    Dispatch a webhook notification to configured services (e.g. Discord, Slack) 
    when an agent requests approval for a sensitive tool execution.
    """
    notification_msg = (
        f"⚠️ Security Alert: Agent `{agent_name}` is requesting approval "
        f"to execute a sensitive tool: `{tool_name}`.\n"
        f"Arguments: ```json\n{args_json}\n```\n"
        f"Please check the terminal to approve or deny."
    )
    
    # 1. Discord Webhook
    discord_webhook_url = os.environ.get("DISCORD_PERMISSION_WEBHOOK") or getattr(creds, "DISCORD_PERMISSION_WEBHOOK", None)
    if discord_webhook_url:
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(discord_webhook_url, json={"content": notification_msg})
        except Exception as e:
            if logger:
                logger.error(f"Failed to send Discord webhook notification: {e}")

    # 2. Slack Webhook
    slack_webhook_url = os.environ.get("SLACK_PERMISSION_WEBHOOK") or getattr(creds, "SLACK_PERMISSION_WEBHOOK", None)
    if slack_webhook_url:
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(slack_webhook_url, json={"text": notification_msg})
        except Exception as e:
            if logger:
                logger.error(f"Failed to send Slack webhook notification: {e}")
