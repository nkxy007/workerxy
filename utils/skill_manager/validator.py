"""
Validator - checks SKILL.md files against the agentskills.io spec
"""

from pathlib import Path
from typing import Optional
from models import (
    Skill, SkillFrontmatter,
    NAME_MAX, DESC_MAX, COMPAT_MAX, VALID_NAME_RE, SPEC_KEYS,
)


class SkillValidationError(Exception):
    """Raised when a SKILL.md does not meet the agentskills.io spec."""
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("\n".join(f"  • {e}" for e in errors))


def validate_skill(skill_path: Path, raise_on_error: bool = True) -> list[str]:
    """
    Validate a skill directory against the agentskills.io spec.

    Args:
        skill_path: Path to the skill directory (must contain SKILL.md)
        raise_on_error: If True, raise SkillValidationError on failure

    Returns:
        List of validation error strings (empty = valid)
    """
    errors: list[str] = []

    # ── 1. Directory / file existence ────────────────────────────────────────
    if not skill_path.is_dir():
        errors.append(f"'{skill_path}' is not a directory")
        if raise_on_error:
            raise SkillValidationError(errors)
        return errors

    skill_file = skill_path / "SKILL.md"
    if not skill_file.exists():
        errors.append("SKILL.md not found in skill directory")
        if raise_on_error:
            raise SkillValidationError(errors)
        return errors

    # ── 2. Parse ─────────────────────────────────────────────────────────────
    try:
        skill = Skill.load(skill_path)
    except Exception as exc:
        errors.append(f"Failed to parse SKILL.md: {exc}")
        if raise_on_error:
            raise SkillValidationError(errors)
        return errors

    fm = skill.frontmatter

    # ── 3. name ──────────────────────────────────────────────────────────────
    if not fm.name:
        errors.append("'name' field is required")
    else:
        if len(fm.name) > NAME_MAX:
            errors.append(f"'name' exceeds {NAME_MAX} characters ({len(fm.name)})")
        if not VALID_NAME_RE.match(fm.name):
            errors.append(
                f"'name' must be lowercase letters/numbers/hyphens, "
                f"no leading/trailing/consecutive hyphens. Got: '{fm.name}'"
            )
        # Directory name must match
        if fm.name != skill_path.name:
            errors.append(
                f"'name' ('{fm.name}') must match directory name ('{skill_path.name}')"
            )

    # ── 4. description ───────────────────────────────────────────────────────
    if not fm.description:
        errors.append("'description' field is required")
    elif len(fm.description) > DESC_MAX:
        errors.append(f"'description' exceeds {DESC_MAX} characters ({len(fm.description)})")
    elif len(fm.description) < 20:
        errors.append("'description' is too short to be useful (< 20 chars)")

    # ── 5. compatibility ─────────────────────────────────────────────────────
    if fm.compatibility and len(fm.compatibility) > COMPAT_MAX:
        errors.append(f"'compatibility' exceeds {COMPAT_MAX} characters")

    # ── 6. metadata must be a mapping ────────────────────────────────────────
    if fm.metadata is not None and not isinstance(fm.metadata, dict):
        errors.append("'metadata' must be a key-value mapping")

    # ── 7. No non-spec top-level keys ────────────────────────────────────────
    import yaml
    raw = yaml.safe_load(skill_file.read_text().split("---", 2)[1]) or {}
    unknown = set(raw.keys()) - SPEC_KEYS
    if unknown:
        errors.append(
            f"Non-spec top-level frontmatter keys found: {sorted(unknown)}. "
            f"Move them under 'metadata:'."
        )

    # ── 8. Body must be non-empty ────────────────────────────────────────────
    if not skill.body.strip():
        errors.append("SKILL.md body (after frontmatter) must not be empty")

    if errors and raise_on_error:
        raise SkillValidationError(errors)

    return errors


def validate_frontmatter_dict(fm: dict) -> list[str]:
    """
    Validate a frontmatter dict before writing it.
    Returns list of error strings.
    """
    errors: list[str] = []
    name = fm.get("name", "")
    desc = fm.get("description", "")

    if not name:
        errors.append("'name' is required")
    elif not VALID_NAME_RE.match(name) or len(name) > NAME_MAX:
        errors.append(f"Invalid 'name': '{name}'")

    if not desc:
        errors.append("'description' is required")
    elif len(desc) > DESC_MAX:
        errors.append(f"'description' too long ({len(desc)} > {DESC_MAX})")

    unknown = set(fm.keys()) - SPEC_KEYS
    if unknown:
        errors.append(f"Non-spec keys must go under 'metadata:': {sorted(unknown)}")

    return errors
