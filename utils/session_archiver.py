"""
session_archiver.py

Provides a fire-and-forget async helper to embed and archive CLI sessions
into the ChromaDB vector store via ArchiverRetriever.

Only HumanMessage and meaningful AIMessage objects are archived — ToolMessage,
SystemMessage, and AI tool-dispatch messages (no content) are filtered out.
"""

import asyncio
import logging
from typing import List, Any, Optional

from langchain_core.messages import HumanMessage, AIMessage

logger = logging.getLogger(__name__)

# Module-level optional import — may be absent in minimal envs (no chromadb/openai).
# Using a module-level name makes it patchable in unit tests.
try:
    from tools_helpers.retriever_archiver import ArchiverRetriever as _ArchiverRetriever
except ImportError:
    _ArchiverRetriever = None  # type: ignore[assignment,misc]

ArchiverRetriever = _ArchiverRetriever  # re-exported so tests can patch this name


def _filter_for_archive(messages: List[Any]) -> List[dict]:
    """
    Filter a LangChain message list down to only human and AI text messages,
    then convert to the {role, content} dicts expected by ArchiverRetriever.

    Excluded:
    - ToolMessage / SystemMessage (any type that is not HumanMessage or AIMessage)
    - AIMessage where content is empty/blank AND tool_calls are present
      (these are the "dispatch" messages that only contain tool invocations,
       not actual conversational text)
    """
    filtered = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            if content.strip():
                filtered.append({"role": "user", "content": content})
        elif isinstance(msg, AIMessage):
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            # Skip AI messages that are purely tool dispatches (no text content)
            has_tool_calls_only = (not content.strip()) and bool(getattr(msg, "tool_calls", None))
            if not has_tool_calls_only and content.strip():
                filtered.append({"role": "assistant", "content": content})
    return filtered


async def archive_session_async(messages: List[Any], session_name: str) -> Optional[str]:
    """
    Embed and archive a session into ChromaDB.

    Args:
        messages:     The LangChain message list from the current session.
        session_name: A human-readable label used as doc_id metadata.

    Returns:
        The ChromaDB doc_id on success, or None on failure.
    """
    if ArchiverRetriever is None:
        logger.warning("[session_archiver] ArchiverRetriever not available (missing deps); skipping archive.")
        return None

    filtered = _filter_for_archive(messages)
    if not filtered:
        logger.info(f"[session_archiver] No archivable messages for '{session_name}'; skipping.")
        return None

    try:
        archiver = ArchiverRetriever()
    except Exception as e:
        logger.warning(f"[session_archiver] ArchiverRetriever init failed (no API key?): {e}")
        return None

    try:
        doc_id = archiver.archive_conversation(
            filtered,
            metadata={"session_name": session_name, "source": "cli_session_save"},
        )
        logger.info(f"[session_archiver] Session '{session_name}' archived with doc_id: {doc_id}")
        return doc_id
    except Exception as e:
        logger.error(f"[session_archiver] archive_conversation failed for '{session_name}': {e}")
        return None


def fire_and_forget_archive(messages: List[Any], session_name: str) -> None:
    """
    Schedule archive_session_async as a fire-and-forget asyncio task so the
    CLI is never blocked waiting for embedding/network I/O.

    Safe to call from any async context. If there is no running event loop
    the archive is simply skipped (e.g., in sync unit-test contexts that
    haven't set up a loop).
    """
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(
            archive_session_async(messages, session_name),
            name=f"archive_session_{session_name}",
        )
        logger.debug(f"[session_archiver] Archive task scheduled for '{session_name}'")
    except RuntimeError:
        # No running event loop — skip silently
        logger.debug("[session_archiver] No running event loop; skipping archive task.")
