"""
SkillScanner - scan a skills directory and update all relevant skills from context
"""

import logging
from pathlib import Path
from typing import Optional

from .llm_client import LLMClient
from .models import Skill, UpdateResult
from .updater import SkillUpdater

logger = logging.getLogger(__name__)


class SkillScanner:
    """
    Scans a directory of skills and updates those relevant to a given context.

    The scanner uses the LLM to decide which skills are relevant before
    attempting any updates — this avoids unnecessary LLM calls for unrelated skills.

    Usage:
        scanner = SkillScanner(skills_dir=Path("skills"))
        results = scanner.scan_and_update(context="<agent output or tool response>")
        for r in results:
            print(r)
    """

    def __init__(
        self,
        skills_dir: Path,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        max_backups: int = 10,
        **model_kwargs,
    ):
        self.skills_dir = Path(skills_dir)
        self._llm = LLMClient(provider=provider, model=model, **model_kwargs)
        self._updater = SkillUpdater(provider=provider, model=model, max_backups=max_backups, **model_kwargs)

    # ── Public API ────────────────────────────────────────────────────────────

    def list_skills(self) -> list[Path]:
        """Return all valid skill directories (those containing SKILL.md)."""
        return [
            p for p in self.skills_dir.iterdir()
            if p.is_dir() and (p / "SKILL.md").exists()
        ]

    def find_relevant_skills(self, context: str) -> list[Path]:
        """
        Ask the LLM which skills in the directory are relevant to this context.
        Returns a list of skill paths that should be checked for updates.
        """
        skills = self.list_skills()
        if not skills:
            logger.info("No skills found in directory")
            return []

        # Build a compact index: name -> description (for the LLM to reason over)
        index: dict[str, str] = {}
        for skill_path in skills:
            try:
                skill = Skill.load(skill_path)
                index[skill_path.name] = skill.frontmatter.description[:200]
            except Exception as exc:
                logger.warning(f"Could not load skill '{skill_path.name}': {exc}")

        if not index:
            return []

        import json
        skill_list = "\n".join(f"- {name}: {desc}" for name, desc in index.items())

        prompt = f"""Given this context from an agent or conversation, which of the listed skills
might need to be updated with new information found in the context?

Context:
<context>
{context[:6000]}
</context>

Available skills:
{skill_list}

Respond with ONLY valid JSON (no markdown fences):
{{
  "relevant_skills": ["skill-name-1", "skill-name-2"]
}}

Return an empty list if no skills are relevant."""

        result = self._llm._json_call(prompt, max_tokens=300, fallback={"relevant_skills": []})
        relevant_names = set(result.get("relevant_skills", []))

        matched = [p for p in skills if p.name in relevant_names]
        logger.info(f"Relevant skills for context: {[p.name for p in matched]}")
        return matched

    def scan_and_update(
        self,
        context: str,
        dry_run: bool = False,
        target_skills: Optional[list[str]] = None,
    ) -> list[UpdateResult]:
        """
        Scan skills and update those relevant to the context.

        Args:
            context:       Raw text from agent output, tool responses, etc.
            dry_run:       If True, compute updates but do NOT write to disk.
            target_skills: Optional list of skill names to restrict the scan to.

        Returns:
            List of UpdateResult objects (one per skill checked).
        """
        if target_skills:
            skills = [
                self.skills_dir / name
                for name in target_skills
                if (self.skills_dir / name / "SKILL.md").exists()
            ]
        else:
            skills = self.find_relevant_skills(context)

        if not skills:
            logger.info("No relevant skills found — nothing to update")
            return []

        results: list[UpdateResult] = []
        for skill_path in skills:
            logger.info(f"Checking skill: {skill_path.name}")
            result = self._updater.update_from_context(
                skill_path=skill_path,
                context=context,
                dry_run=dry_run,
            )
            results.append(result)
            logger.info(str(result))

        return results

    def report(self, results: list[UpdateResult]) -> str:
        """Format scan results as a human-readable report."""
        if not results:
            return "No skills were checked."

        lines = [f"Skill Update Report ({len(results)} skill(s) checked)", "=" * 50]
        updated = [r for r in results if r.updated]
        skipped = [r for r in results if not r.updated]

        if updated:
            lines.append(f"\n✓ Updated ({len(updated)}):")
            for r in updated:
                prefix = "[DRY RUN] " if r.dry_run else ""
                lines.append(f"  {prefix}{r.skill_name}: {r.reason}")
                for fact in r.extracted_facts:
                    lines.append(f"    • {fact}")

        if skipped:
            lines.append(f"\n— No update needed ({len(skipped)}):")
            for r in skipped:
                lines.append(f"  {r.skill_name}: {r.reason}")

        return "\n".join(lines)
