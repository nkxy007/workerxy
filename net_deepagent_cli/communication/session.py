import json
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from langchain_core.messages import message_to_dict, messages_from_dict

SESSIONS_DIR = Path.home() / ".net_deepagent" / "online_chat_sessions"
TOKEN_THRESHOLD = 3000      # trigger summarisation before hitting LLM context limit
RECENT_EXCHANGES_TO_KEEP = 3  # raw exchanges preserved alongside the summary

def _session_path(session_id: Any) -> Path:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    p = SESSIONS_DIR / f"{session_id}.json"
    return p

def estimate_tokens(messages: List[Any]) -> int:
    """Approximate token count — 4 chars ≈ 1 token."""
    total_chars = 0
    for m in messages:
        content = getattr(m, "content", "")
        if isinstance(content, str):
            total_chars += len(content)
        elif isinstance(content, list):
            # Handle list of content blocks if necessary
            for block in content:
                if isinstance(block, dict) and "text" in block:
                    total_chars += len(block["text"])
    return total_chars // 4

def load_session(session_id: Any) -> Dict[str, Any]:
    """
    Load session for a channel/user.
    Returns: { "summary": str | None, "messages": list[BaseMessage] }
    """
    path = _session_path(session_id)
    if not path.exists():
        return {"summary": None, "messages": []}
    
    try:
        with open(path, "r") as f:
            data = json.load(f)
            summary = data.get("summary")
            serialized_messages = data.get("messages", [])
            messages = messages_from_dict(serialized_messages)
            return {"summary": summary, "messages": messages}
    except Exception as e:
        # If corrupt or old format, return empty
        return {"summary": None, "messages": []}

def save_session(session_id: Any, session: Dict[str, Any]):
    """Persist session to disk."""
    path = _session_path(session_id)
    try:
        serialized_messages = [message_to_dict(m) for m in session["messages"]]
        data = {
            "summary": session.get("summary"),
            "messages": serialized_messages
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error in save_session: {e}")

def clear_session(session_id: Any):
    """Reset conversation for a channel."""
    path = _session_path(session_id)
    if path.exists():
        path.unlink()

def filter_tool_messages(messages: List[Any]) -> List[Any]:
    """
    Strip all tool call inputs and tool results from history.
    Only keep human and assistant text messages, cast to clean strings.
    """
    from langchain_core.messages import HumanMessage, AIMessage
    clean = []
    for m in messages:
        if isinstance(m, HumanMessage):
            content = m.content
            if isinstance(content, list):
                content = "\n".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
            clean.append(HumanMessage(content=content))
            
        elif isinstance(m, AIMessage):
            content = m.content
            if isinstance(content, list):
                parts = []
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "text":
                        parts.append(b.get("text", ""))
                    elif isinstance(b, str):
                        parts.append(b)
                content = "\n".join(parts)
            
            content = str(content).strip() if content else ""
            if content:
                # Create a fresh AIMessage without tool_calls
                clean.append(AIMessage(content=content))
                
    return clean

def build_llm_messages(session: Dict[str, Any]) -> List[Any]:
    """
    Build the message list to send to the LLM.
    If a summary exists, prepend it as a system message.
    """
    from langchain_core.messages import SystemMessage
    messages = filter_tool_messages(session["messages"])

    if session.get("summary"):
        system_message = SystemMessage(
            content=(
                f"Summary of the conversation so far:\n{session['summary']}\n\n"
                "The most recent exchanges follow in full."
            )
        )
        return [system_message] + messages

    return messages
