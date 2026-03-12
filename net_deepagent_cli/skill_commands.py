"""
Skill command handlers for /skills add and /skills update.

Imports SkillCreator and SkillUpdater from utils/skill_manager via sys.path
injection so the module works without install and without changing its imports.
"""

import sys
import logging
import asyncio
from pathlib import Path
from typing import Optional, List

# ── Import skill_manager without breaking its standalone script usage ─────────
_skill_manager_dir = Path(__file__).parent.parent / "utils" / "skill_manager"
if str(_skill_manager_dir) not in sys.path:
    sys.path.insert(0, str(_skill_manager_dir))

from creator import SkillCreator          # type: ignore
from updater import SkillUpdater          # type: ignore

logger = logging.getLogger(__name__)

# Default skill updated when no skill name is given
DEFAULT_UPDATE_SKILL = "network-facts-and-procedures"


def _skills_dir(agent_name: str) -> Path:
    """Return the agent's personal skills directory."""
    return Path.home() / ".net-deepagent" / agent_name / "skills"


def _build_context_from_messages(messages: List) -> str:
    """
    Build a text context string from a message list.

    Rules (per user spec):
      - Include ALL HumanMessages.
      - Include the last 10 AIMessages.
      - Skip tool, system, and function messages to save tokens.
    """
    human_msgs = []
    ai_msgs = []

    for m in messages:
        msg_type = getattr(m, "type", "")
        content = str(getattr(m, "content", "")).strip()
        if not content:
            continue

        if msg_type == "human":
            human_msgs.append(f"USER: {content}")
        elif msg_type == "ai":
            # Skip pure tool-call stubs (no text content)
            if content:
                ai_msgs.append(f"ASSISTANT: {content}")

    # Keep all human messages, last 10 AI messages
    selected_ai = ai_msgs[-10:] if len(ai_msgs) > 10 else ai_msgs

    return "\n\n".join(human_msgs + selected_ai)


async def _background_skill_creation(ui, doc_path, document_text, skill_name_hint, output_dir):
    try:
        creator = SkillCreator()
        skill_path = await asyncio.to_thread(
            creator.from_document,
            document=document_text,
            skill_name=skill_name_hint,
            output_dir=output_dir,
        )
        ui.print_message(
            f"✅ Skill [bold green]{skill_path.name}[/bold green] created at "
            f"[dim]{skill_path}[/dim]",
            role="system",
        )
    except FileExistsError:
        ui.print_message(
            f"Skill [bold yellow]{skill_name_hint}[/bold yellow] already exists. "
            "Use a different name or delete the existing skill directory first.",
            role="error",
        )
    except Exception as exc:
        logger.error(f"Skill creation failed: {exc}", exc_info=True)
        ui.print_message(f"❌ Skill creation failed: {exc}", role="error")

async def handle_skill_add(doc_path_str: str, skill_name_hint: Optional[str], agent_name: str, ui):
    """
    Handle /skills add <doc_path> [skill_name].
    Uses SkillCreator to generate a new LLM-powered SKILL.md from a document.
    Returns the background task so callers can await if needed.
    """
    doc_path = Path(doc_path_str)
    if not doc_path.exists():
        ui.print_message(f"Document not found: [bold red]{doc_path_str}[/bold red]", role="error")
        return None

    # Derive skill name from filename if not provided
    if not skill_name_hint:
        skill_name_hint = doc_path.stem
        prompted = await ui.prompt_simple(
            f"[bold blue]Skill name[/] ([dim]{skill_name_hint}[/dim]): "
        )
        if prompted.strip():
            skill_name_hint = prompted.strip()

    output_dir = _skills_dir(agent_name)
    output_dir.mkdir(parents=True, exist_ok=True)

    ui.print_message(
        f"📖 Reading [bold cyan]{doc_path.name}[/bold cyan] and generating skill "
        f"[bold yellow]{skill_name_hint}[/bold yellow]... (this may take a moment)",
        role="system",
    )

    try:
        document_text = doc_path.read_text(encoding="utf-8", errors="ignore")
        return asyncio.create_task(
            _background_skill_creation(ui, doc_path, document_text, skill_name_hint, output_dir)
        )
    except Exception as exc:
        ui.print_message(f"Failed to read source document: {exc}", role="error")
        return None


async def _background_skill_update(ui, skill_name, skill_path, context, dry_run):
    try:
        updater = SkillUpdater()
        result = await asyncio.to_thread(
            updater.update_from_context,
            skill_path=skill_path,
            context=context,
            dry_run=dry_run,
        )

        if result.updated:
            facts_text = ""
            if result.extracted_facts:
                facts_text = "\n" + "\n".join(f"  • {f}" for f in result.extracted_facts)
            dry_tag = "[dim](dry run — not written)[/dim] " if dry_run else ""
            ui.print_message(
                f"✅ {dry_tag}[bold green]{skill_name}[/bold green] updated: {result.reason}{facts_text}",
                role="system",
            )
        else:
            ui.print_message(
                f"ℹ️ No update needed for [bold yellow]{skill_name}[/bold yellow]: {result.reason}",
                role="system",
            )
    except Exception as exc:
        logger.error(f"Skill update failed: {exc}", exc_info=True)
        ui.print_message(f"❌ Skill update failed: {exc}", role="error")


async def handle_skill_update(
    skill_name: Optional[str],
    source: Optional[str],
    dry_run: bool,
    agent_name: str,
    ui,
    messages: List,
):
    """
    Handle /skills update [skill_name] [source] [--dry-run].

    - skill_name defaults to DEFAULT_UPDATE_SKILL.
    - source: path to a document, or None to use conversation context.
    - Context: all human messages + last 10 AI messages.
    Returns the background task so callers can await if needed.
    """
    skill_name = skill_name or DEFAULT_UPDATE_SKILL

    # Resolve skill path
    skill_path = _skills_dir(agent_name) / skill_name
    if not (skill_path / "SKILL.md").exists():
        ui.print_message(
            f"Skill [bold red]{skill_name}[/bold red] not found at [dim]{skill_path}[/dim].\n"
            f"Create it first with: [bold]/skills add <doc> {skill_name}[/bold]",
            role="error",
        )
        return None

    # Build context
    if source and source != "--dry-run":
        src_path = Path(source)
        if not src_path.exists():
            ui.print_message(f"Source file [bold red]{source}[/bold red] not found.", role="error")
            return None
        try:
            context = src_path.read_text(encoding="utf-8", errors="ignore")
            ui.print_message(
                f"📄 Using document [bold cyan]{src_path.name}[/bold cyan] as context.",
                role="system",
            )
        except Exception as exc:
            ui.print_message(f"Failed to read source: {exc}", role="error")
            return None
    else:
        if not messages:
            ui.print_message("No conversation messages available to use as context.", role="warning")
            return None
        context = _build_context_from_messages(messages)
        msg_summary = f"all user messages + last 10 AI messages ({len(context)} chars)"
        ui.print_message(
            f"💬 Using current session context: {msg_summary}",
            role="system",
        )

    dry_label = "[DRY RUN] " if dry_run else ""
    ui.print_message(
        f"🔍 {dry_label}Checking [bold yellow]{skill_name}[/bold yellow] for updates...",
        role="system",
    )

    return asyncio.create_task(
        _background_skill_update(ui, skill_name, skill_path, context, dry_run)
    )
