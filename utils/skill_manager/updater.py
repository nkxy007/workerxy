"""
SkillUpdater - detects new info in agent context and updates existing skills
"""

import logging
from pathlib import Path
from typing import Optional

from backup import BackupManager
from llm_client import LLMClient
from models import Skill, UpdateResult
from validator import validate_skill, SkillValidationError

logger = logging.getLogger(__name__)


class SkillUpdater:
    """
    Detects new information in conversation/agent context and updates
    an existing SKILL.md file (agentskills.io spec compliant).

    Usage:
        updater = SkillUpdater()
        result = updater.update_from_context(
            skill_path=Path("skills/my-skill"),
            context="We use Juniper Mist. Org ID: abc-123. API base: https://api.mist.com/api/v1",
        )
        print(result)
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        max_backups: int = 10,
        max_retries: int = 2,
        **model_kwargs,
    ):
        self._llm = LLMClient(provider=provider, model=model, **model_kwargs)
        self._max_backups = max_backups
        self._max_retries = max_retries

    # ── Public API ────────────────────────────────────────────────────────────

    def update_from_context(
        self,
        skill_path: Path,
        context: str,
        dry_run: bool = False,
        force: bool = False,
    ) -> UpdateResult:
        """
        Analyse `context` and update the skill if new information is found.

        Args:
            skill_path: Directory containing SKILL.md
            context:    Raw text from agent output, tool responses, conversation, etc.
            dry_run:    If True, compute the update but do NOT write to disk.
            force:      Skip LLM detection and always apply the update.

        Returns:
            UpdateResult describing what happened.
        """
        skill_path = Path(skill_path)
        skill_name = skill_path.name

        # Load & validate
        try:
            skill = Skill.load(skill_path)
        except Exception as exc:
            return UpdateResult(skill_name=skill_name, updated=False, reason=f"Load failed: {exc}")

        # ── Phase 1: detect ──────────────────────────────────────────────────
        if force:
            detection = {
                "should_update": True,
                "reason": "force=True bypassed detection",
                "extracted_facts": [context],
            }
        else:
            detection = self._llm.detect_new_info(skill.body, context)

        if not detection.get("should_update"):
            return UpdateResult(
                skill_name=skill_name,
                updated=False,
                reason=detection.get("reason", "No new information detected"),
                dry_run=dry_run,
            )

        facts = detection.get("extracted_facts", [])
        if not facts:
            return UpdateResult(
                skill_name=skill_name,
                updated=False,
                reason="Detection flagged update but extracted no facts",
                dry_run=dry_run,
            )

        logger.info(f"[{skill_name}] Detected {len(facts)} new fact(s): {facts}")

        # ── Phase 2: rewrite ─────────────────────────────────────────────────
        new_body = self._llm.rewrite_body(skill.body, facts, skill_name)

        if dry_run:
            return UpdateResult(
                skill_name=skill_name,
                updated=True,
                reason=detection.get("reason", ""),
                extracted_facts=facts,
                dry_run=True,
            )

        # ── Phase 3: backup + write (with validation retry) ──────────────────
        bm = BackupManager(skill_path, max_backups=self._max_backups)
        backup_path = bm.create()

        current_body = new_body
        for attempt in range(1, self._max_retries + 2):
            skill.body = current_body
            skill.save(bump_update_count=True)

            post_errors = validate_skill(skill_path, raise_on_error=False)
            if not post_errors:
                # Written and valid
                break

            logger.warning(
                f"[{skill_name}] Post-write validation failed (attempt {attempt}): "
                + "; ".join(post_errors)
            )
            if attempt > self._max_retries:
                # Exhausted retries — roll back to backup
                bm.rollback(steps=1)
                logger.error(f"[{skill_name}] Rolled back to backup after {self._max_retries} failed validation attempts")
                return UpdateResult(
                    skill_name=skill_name,
                    updated=False,
                    reason=f"Validation failed after {self._max_retries} retries — rolled back: " + "; ".join(post_errors),
                    dry_run=False,
                )
            # Ask LLM to fix the body and retry
            current_body = self._llm.fix_body(current_body, post_errors, skill_name)

        logger.info(f"[{skill_name}] Skill updated successfully")

        return UpdateResult(
            skill_name=skill_name,
            updated=True,
            reason=detection.get("reason", ""),
            backup_path=backup_path,
            extracted_facts=facts,
            dry_run=False,
        )

    def rollback(self, skill_path: Path, steps: int = 1) -> bool:
        """
        Rollback a skill to a previous backup.

        Args:
            skill_path: Directory containing SKILL.md
            steps:      How many versions back to go (default: 1 = most recent backup)

        Returns:
            True if rollback succeeded.
        """
        bm = BackupManager(Path(skill_path), max_backups=self._max_backups)
        return bm.rollback(steps=steps)

    def list_backups(self, skill_path: Path) -> list[Path]:
        """Return list of available backup files for a skill, newest first."""
        return BackupManager(Path(skill_path)).list_backups()
