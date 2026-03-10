"""
SkillCreator - generate a new spec-compliant skill from a document or scratch
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from llm_client import LLMClient
from models import Skill, SkillFrontmatter
from validator import validate_skill, validate_frontmatter_dict, SkillValidationError, VALID_NAME_RE

logger = logging.getLogger(__name__)


def _slugify(text: str) -> str:
    """Convert arbitrary text to a valid agentskills.io skill name."""
    s = text.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    s = re.sub(r"-{2,}", "-", s)
    return s[:64]


class SkillCreator:
    """
    Generate a new agentskills.io-compliant skill directory from:
      - A document (PDF text, markdown, plain text)
      - Or minimal user-supplied information

    Usage:
        creator = SkillCreator()

        # From a document
        skill_path = creator.from_document(
            document="<paste your API docs here>",
            skill_name="juniper-mist-wifi-api",
            output_dir=Path("skills"),
        )

        # From scratch (you supply description + instructions)
        skill_path = creator.from_scratch(
            skill_name="my-new-skill",
            description="Does X when Y.",
            body_markdown="## Overview\n...",
            output_dir=Path("skills"),
        )
    """

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None, max_retries: int = 2, **model_kwargs):
        self._llm = LLMClient(provider=provider, model=model, **model_kwargs)
        self._max_retries = max_retries

    # ── Public API ────────────────────────────────────────────────────────────

    def from_document(
        self,
        document: str,
        skill_name: str,
        output_dir: Path,
        description: Optional[str] = None,
        license_text: Optional[str] = None,
        compatibility: Optional[str] = None,
        author: Optional[str] = None,
        overwrite: bool = False,
    ) -> Path:
        """
        Bootstrap a new skill from a source document (API docs, runbook, etc.).

        Args:
            document:      Raw document text to extract instructions from.
            skill_name:    Desired skill name (will be slugified to meet spec).
            output_dir:    Parent directory; skill created at output_dir/skill_name/.
            description:   Optional override; LLM generates one if omitted.
            license_text:  Optional license string.
            compatibility: Optional compatibility string.
            author:        Optional author for metadata.
            overwrite:     If False (default), raise if skill directory already exists.

        Returns:
            Path to the created skill directory.
        """
        skill_name = _slugify(skill_name)
        output_dir = Path(output_dir)
        skill_path = output_dir / skill_name

        self._check_exists(skill_path, overwrite)

        # Generate description if not supplied
        if not description:
            logger.info(f"[{skill_name}] Generating description...")
            description = self._llm.suggest_description(document, skill_name)

        # Generate body
        logger.info(f"[{skill_name}] Generating skill body from document...")
        body = self._llm.create_skill_body(document, skill_name, description)

        return self._write_skill(
            skill_path=skill_path,
            skill_name=skill_name,
            description=description,
            body=body,
            license_text=license_text,
            compatibility=compatibility,
            author=author,
        )

    def from_scratch(
        self,
        skill_name: str,
        description: str,
        body_markdown: str,
        output_dir: Path,
        license_text: Optional[str] = None,
        compatibility: Optional[str] = None,
        author: Optional[str] = None,
        overwrite: bool = False,
    ) -> Path:
        """
        Create a skill from manually supplied content (no LLM generation).

        Args:
            skill_name:     Desired skill name (will be slugified).
            description:    Skill description (max 1024 chars).
            body_markdown:  Full markdown body for SKILL.md.
            output_dir:     Parent directory.
            license_text:   Optional license.
            compatibility:  Optional compatibility string.
            author:         Optional author for metadata.
            overwrite:      If False, raise if directory already exists.

        Returns:
            Path to the created skill directory.
        """
        skill_name = _slugify(skill_name)
        output_dir = Path(output_dir)
        skill_path = output_dir / skill_name

        self._check_exists(skill_path, overwrite)

        return self._write_skill(
            skill_path=skill_path,
            skill_name=skill_name,
            description=description,
            body=body_markdown,
            license_text=license_text,
            compatibility=compatibility,
            author=author,
        )

    def create_optional_dirs(self, skill_path: Path):
        """Create the optional scripts/, references/, assets/ directories."""
        for d in ("scripts", "references", "assets"):
            (skill_path / d).mkdir(exist_ok=True)
            logger.debug(f"Created {skill_path / d}/")

    # ── Internal ──────────────────────────────────────────────────────────────

    def _write_skill(
        self,
        skill_path: Path,
        skill_name: str,
        description: str,
        body: str,
        license_text: Optional[str],
        compatibility: Optional[str],
        author: Optional[str],
    ) -> Path:
        skill_path.mkdir(parents=True, exist_ok=True)

        metadata: dict = {
            "created": datetime.now().strftime("%Y-%m-%d"),
            "total-updates": 0,
        }
        if author:
            metadata["author"] = author

        # ── Retry loop: fix description / body if validation fails ────────────
        for attempt in range(1, self._max_retries + 2):  # attempts: 1 .. max_retries+1
            # Pre-validate / fix description
            desc_errors = []
            from validator import validate_frontmatter_dict  # already imported at top
            desc_fm = {"name": skill_name, "description": description}
            pre_errors = validate_frontmatter_dict(desc_fm)
            # Only surface description-related errors at this stage
            desc_errors = [e for e in pre_errors if "description" in e.lower()]
            if desc_errors:
                if attempt > self._max_retries:
                    raise SkillValidationError(desc_errors)
                logger.warning(
                    f"[{skill_name}] Description failed validation (attempt {attempt}): "
                    + "; ".join(desc_errors)
                )
                description = self._llm.fix_description(description, desc_errors, skill_name)
                continue  # re-validate with new description

            fm = SkillFrontmatter(
                name=skill_name,
                description=description,
                license=license_text,
                compatibility=compatibility,
                metadata=metadata,
            )

            # Pre-validate full frontmatter
            fm_errors = validate_frontmatter_dict(fm.to_dict())
            if fm_errors:
                if attempt > self._max_retries:
                    raise SkillValidationError(fm_errors)
                logger.warning(
                    f"[{skill_name}] Frontmatter failed validation (attempt {attempt}): "
                    + "; ".join(fm_errors)
                )
                description = self._llm.fix_description(description, fm_errors, skill_name)
                continue

            # Write skill
            skill = Skill(path=skill_path, frontmatter=fm, body=body)
            skill.save(bump_update_count=False)

            # Post-write validation (checks body, unknown keys, name/dir match, etc.)
            post_errors = validate_skill(skill_path, raise_on_error=False)
            if post_errors:
                if attempt > self._max_retries:
                    raise SkillValidationError(post_errors)
                logger.warning(
                    f"[{skill_name}] Post-write validation failed (attempt {attempt}): "
                    + "; ".join(post_errors)
                )
                body = self._llm.fix_body(body, post_errors, skill_name)
                continue  # retry with fixed body

            # All good
            logger.info(f"[{skill_name}] Skill created and validated at: {skill_path}")
            return skill_path

        # Should not reach here, but guard:
        raise SkillValidationError([f"Skill '{skill_name}' failed validation after {self._max_retries} retries"])

    @staticmethod
    def _check_exists(skill_path: Path, overwrite: bool):
        if skill_path.exists() and not overwrite:
            raise FileExistsError(
                f"Skill directory already exists: {skill_path}. "
                "Pass overwrite=True to replace it."
            )
