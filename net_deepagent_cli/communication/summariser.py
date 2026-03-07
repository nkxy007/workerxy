import os
import sys
from pathlib import Path
from typing import Dict, Any

# Add project root to path to import utils and creds
sys.path.append(str(Path(__file__).parent.parent.parent))

import creds
from utils.llm_provider import LLMFactory
from net_deepagent_cli.communication.session import filter_tool_messages

# Set environment variables for LLMFactory if not already set
os.environ["OPENAI_API_KEY"] = creds.OPENAI_KEY
os.environ["ANTHROPIC_API_KEY"] = creds.ANTHROPIC_KEY

async def summarise_session(session: Dict[str, Any], model_name: str = "gpt-4o-mini") -> str:
    """
    Ask the LLM to summarise the current session.
    Includes any prior summary and all filtered messages.
    """
    parts = []

    if session.get("summary"):
        parts.append(f"Previous summary:\n{session['summary']}")

    messages = filter_tool_messages(session["messages"])
    if messages:
        conversation_text = ""
        for m in messages:
            role = m.type.upper() if hasattr(m, "type") else "UNKNOWN"
            content = m.content if isinstance(m.content, str) else str(m.content)
            conversation_text += f"{role}: {content}\n"
        parts.append(f"Recent conversation:\n{conversation_text}")

    if not parts:
        return ""

    prompt = (
        "You are summarising a network operations conversation between a network engineer "
        "and an AI agent. Produce a concise summary that captures: the network issues discussed, "
        "devices investigated, findings, and any actions taken or recommended. "
        "Be specific about device names, IPs, and outcomes — these details matter for follow-up questions.\n\n"
        + "\n\n".join(parts)
        + "\n\nSummary:"
    )

    try:
        llm = LLMFactory.get_llm(model_name)
        response = await llm.ainvoke(prompt)
        return response.content.strip()
    except Exception as e:
        # Fallback in case of error
        return session.get("summary") or "Conversation summary unavailable."
