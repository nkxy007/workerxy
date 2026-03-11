"""
Shared data models for skill-manager
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
import yaml
import re


# ── Spec constraints ─────────────────────────────────────────────────────────
NAME_MAX = 64
DESC_MAX = 1024
COMPAT_MAX = 500
VALID_NAME_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')

# Frontmatter keys recognised by the spec; everything else must live under metadata:
SPEC_KEYS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}


@dataclass
class SkillFrontmatter:
    name: str
    description: str
    license: Optional[str] = None
    compatibility: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    allowed_tools: Optional[str] = None

    def to_dict(self) -> dict:
        d: dict = {
            "name": self.name,
            "description": self.description,
        }
        if self.license:
            d["license"] = self.license
        if self.compatibility:
            d["compatibility"] = self.compatibility
        if self.metadata:
            d["metadata"] = self.metadata
        if self.allowed_tools:
            d["allowed-tools"] = self.allowed_tools
        return d

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), default_flow_style=False, allow_unicode=True)

    @classmethod
    def from_dict(cls, d: dict) -> "SkillFrontmatter":
        return cls(
            name=d.get("name", ""),
            description=d.get("description", ""),
            license=d.get("license"),
            compatibility=d.get("compatibility"),
            metadata=d.get("metadata") or {},
            allowed_tools=d.get("allowed-tools"),
        )


@dataclass
class Skill:
    path: Path
    frontmatter: SkillFrontmatter
    body: str

    @property
    def skill_file(self) -> Path:
        return self.path / "SKILL.md"

    @classmethod
    def load(cls, skill_path: Path) -> "Skill":
        content = (skill_path / "SKILL.md").read_text(encoding="utf-8")
        fm, body = _split_frontmatter(content)
        return cls(path=skill_path, frontmatter=SkillFrontmatter.from_dict(fm), body=body)

    def save(self, bump_update_count: bool = True):
        if bump_update_count:
            meta = self.frontmatter.metadata
            meta["last-updated"] = datetime.now().strftime("%Y-%m-%d")
            meta["total-updates"] = meta.get("total-updates", 0) + 1

        raw = f"---\n{self.frontmatter.to_yaml()}---\n{self.body.lstrip()}"
        self.skill_file.write_text(raw, encoding="utf-8")

    def full_content(self) -> str:
        return self.skill_file.read_text(encoding="utf-8")


@dataclass
class UpdateResult:
    skill_name: str
    updated: bool
    reason: str
    backup_path: Optional[Path] = None
    extracted_facts: list = field(default_factory=list)
    dry_run: bool = False

    def __str__(self) -> str:
        status = "[DRY RUN] " if self.dry_run else ""
        action = "Updated" if self.updated else "No update"
        return f"{status}{action} '{self.skill_name}': {self.reason}"


def _split_frontmatter(content: str) -> tuple[dict, str]:
    """Split SKILL.md into (frontmatter_dict, body_str)."""
    if not content.startswith("---"):
        raise ValueError("SKILL.md must begin with YAML frontmatter (---)")
    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ValueError("Malformed frontmatter: missing closing ---")
    fm = yaml.safe_load(parts[1]) or {}
    return fm, parts[2]
