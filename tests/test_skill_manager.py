"""
Tests for skill-manager

Run with:  python -m pytest tests/ -v
"""

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import yaml

# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_SKILL_MD = """\
---
name: test-skill
description: A test skill for unit testing. Use when running tests.
metadata:
  author: test
  version: "1.0"
  created: "2026-01-01"
  total-updates: 0
---

## Overview

This skill does test things.

## Authentication

Use `Authorization: Bearer <TOKEN>`.

## Common Operations

### List items
GET /items
"""


@pytest.fixture
def skill_dir(tmp_path):
    """Create a valid skill directory in a temp location."""
    skill_path = tmp_path / "test-skill"
    skill_path.mkdir()
    (skill_path / "SKILL.md").write_text(SAMPLE_SKILL_MD)
    return skill_path


@pytest.fixture
def skills_root(tmp_path):
    """Create a skills root with two sample skills."""
    for name in ("skill-alpha", "skill-beta"):
        p = tmp_path / name
        p.mkdir()
        (p / "SKILL.md").write_text(
            SAMPLE_SKILL_MD.replace("test-skill", name).replace(
                "A test skill for unit testing. Use when running tests.",
                f"Skill {name}. Use for {name} related tasks.",
            )
        )
    return tmp_path


# ── models ────────────────────────────────────────────────────────────────────

class TestModels:
    def test_load_skill(self, skill_dir):
        from skill_manager.models import Skill
        skill = Skill.load(skill_dir)
        assert skill.frontmatter.name == "test-skill"
        assert "test" in skill.frontmatter.description
        assert "## Overview" in skill.body

    def test_save_roundtrip(self, skill_dir):
        from skill_manager.models import Skill
        skill = Skill.load(skill_dir)
        original_body = skill.body
        skill.body = original_body + "\n## New Section\nAdded."
        skill.save(bump_update_count=True)

        reloaded = Skill.load(skill_dir)
        assert "New Section" in reloaded.body
        assert reloaded.frontmatter.metadata["total-updates"] == 1
        assert reloaded.frontmatter.metadata["last-updated"]

    def test_frontmatter_to_dict_excludes_none(self, skill_dir):
        from skill_manager.models import Skill
        skill = Skill.load(skill_dir)
        d = skill.frontmatter.to_dict()
        assert "license" not in d
        assert "compatibility" not in d

    def test_missing_frontmatter_raises(self, tmp_path):
        from skill_manager.models import Skill, _split_frontmatter
        with pytest.raises(ValueError, match="frontmatter"):
            _split_frontmatter("No frontmatter here")


# ── validator ─────────────────────────────────────────────────────────────────

class TestValidator:
    def test_valid_skill_passes(self, skill_dir):
        from skill_manager.validator import validate_skill
        errors = validate_skill(skill_dir, raise_on_error=False)
        assert errors == [], f"Unexpected errors: {errors}"

    def test_missing_name_fails(self, tmp_path):
        from skill_manager.validator import validate_skill
        p = tmp_path / "bad-skill"
        p.mkdir()
        (p / "SKILL.md").write_text(
            "---\ndescription: Missing name field.\n---\n## Body\nContent here."
        )
        errors = validate_skill(p, raise_on_error=False)
        assert any("name" in e for e in errors)

    def test_invalid_name_chars_fails(self, tmp_path):
        from skill_manager.validator import validate_skill
        p = tmp_path / "Bad_Skill"
        p.mkdir()
        (p / "SKILL.md").write_text(
            "---\nname: Bad_Skill\ndescription: Has underscores and uppercase.\n---\n## Body\nContent."
        )
        errors = validate_skill(p, raise_on_error=False)
        assert any("name" in e for e in errors)

    def test_name_directory_mismatch_fails(self, tmp_path):
        from skill_manager.validator import validate_skill
        p = tmp_path / "my-skill"
        p.mkdir()
        (p / "SKILL.md").write_text(
            "---\nname: different-name\ndescription: Name does not match directory.\n---\n## Body\nContent."
        )
        errors = validate_skill(p, raise_on_error=False)
        assert any("match" in e for e in errors)

    def test_non_spec_top_level_key_fails(self, tmp_path):
        from skill_manager.validator import validate_skill
        p = tmp_path / "extra-keys"
        p.mkdir()
        (p / "SKILL.md").write_text(
            "---\nname: extra-keys\ndescription: Has extra keys outside metadata.\nauthor: bob\n---\n## Body\nContent."
        )
        errors = validate_skill(p, raise_on_error=False)
        assert any("metadata" in e for e in errors)

    def test_raises_on_error(self, tmp_path):
        from skill_manager.validator import validate_skill, SkillValidationError
        p = tmp_path / "broken"
        p.mkdir()
        (p / "SKILL.md").write_text("no frontmatter")
        with pytest.raises(SkillValidationError):
            validate_skill(p, raise_on_error=True)

    def test_empty_body_fails(self, tmp_path):
        from skill_manager.validator import validate_skill
        p = tmp_path / "empty-body"
        p.mkdir()
        (p / "SKILL.md").write_text(
            "---\nname: empty-body\ndescription: Has valid frontmatter but empty body.\n---\n   \n"
        )
        errors = validate_skill(p, raise_on_error=False)
        assert any("body" in e for e in errors)


# ── backup ────────────────────────────────────────────────────────────────────

class TestBackupManager:
    def test_create_backup(self, skill_dir):
        from skill_manager.backup import BackupManager
        bm = BackupManager(skill_dir)
        backup_path = bm.create()
        assert backup_path is not None
        assert backup_path.exists()

    def test_rollback(self, skill_dir):
        from skill_manager.backup import BackupManager
        from skill_manager.models import Skill
        bm = BackupManager(skill_dir)
        bm.create()

        # Corrupt the skill
        (skill_dir / "SKILL.md").write_text("---\nname: test-skill\ndescription: Corrupted.\n---\nBroken.")

        ok = bm.rollback()
        assert ok

        skill = Skill.load(skill_dir)
        assert "Overview" in skill.body

    def test_max_backups_pruning(self, skill_dir):
        from skill_manager.backup import BackupManager
        bm = BackupManager(skill_dir, max_backups=3)
        for _ in range(6):
            bm.create()
        backups = bm.list_backups()
        assert len(backups) <= 3

    def test_rollback_no_backups(self, tmp_path):
        from skill_manager.backup import BackupManager
        p = tmp_path / "empty-skill"
        p.mkdir()
        bm = BackupManager(p)
        assert bm.rollback() is False


# ── creator ───────────────────────────────────────────────────────────────────

class TestSkillCreator:
    def test_from_scratch(self, tmp_path):
        from skill_manager.creator import SkillCreator
        creator = SkillCreator()
        skill_path = creator.from_scratch(
            skill_name="my new skill",  # Will be slugified
            description="Does something useful. Use when you need to do that thing.",
            body_markdown="## Overview\nThis skill does stuff.\n\n## Steps\n1. Do this.\n2. Do that.",
            output_dir=tmp_path,
        )
        assert skill_path.exists()
        assert skill_path.name == "my-new-skill"
        assert (skill_path / "SKILL.md").exists()

    def test_slugify(self):
        from skill_manager.creator import _slugify
        assert _slugify("My Cool Skill!") == "my-cool-skill"
        assert _slugify("juniper--mist API") == "juniper-mist-api"
        assert _slugify("  leading spaces  ") == "leading-spaces"

    def test_overwrite_protection(self, tmp_path):
        from skill_manager.creator import SkillCreator
        creator = SkillCreator()
        creator.from_scratch(
            skill_name="dupe",
            description="First version. Use when testing duplicates.",
            body_markdown="## Body\nContent.",
            output_dir=tmp_path,
        )
        with pytest.raises(FileExistsError):
            creator.from_scratch(
                skill_name="dupe",
                description="Second version. Use when testing duplicates.",
                body_markdown="## Body\nContent.",
                output_dir=tmp_path,
            )

    def test_overwrite_allowed(self, tmp_path):
        from skill_manager.creator import SkillCreator
        creator = SkillCreator()
        creator.from_scratch(
            skill_name="overwritable",
            description="First version. Use to test overwriting.",
            body_markdown="## Body\nOriginal.",
            output_dir=tmp_path,
        )
        skill_path = creator.from_scratch(
            skill_name="overwritable",
            description="Second version. Use to test overwriting.",
            body_markdown="## Body\nReplaced.",
            output_dir=tmp_path,
            overwrite=True,
        )
        content = (skill_path / "SKILL.md").read_text()
        assert "Replaced" in content

    def test_create_optional_dirs(self, tmp_path):
        from skill_manager.creator import SkillCreator
        creator = SkillCreator()
        skill_path = creator.from_scratch(
            skill_name="with-dirs",
            description="Has optional directories. Use to test directory creation.",
            body_markdown="## Body\nContent.",
            output_dir=tmp_path,
        )
        creator.create_optional_dirs(skill_path)
        for d in ("scripts", "references", "assets"):
            assert (skill_path / d).is_dir()

    @patch("skill_manager.llm_client.LLMClient.suggest_description")
    @patch("skill_manager.llm_client.LLMClient.create_skill_body")
    def test_from_document(self, mock_body, mock_desc, tmp_path):
        mock_desc.return_value = "Generated description. Use when working with docs."
        mock_body.return_value = "## Overview\nGenerated body."

        from skill_manager.creator import SkillCreator
        creator = SkillCreator()
        skill_path = creator.from_document(
            document="Some API documentation content here...",
            skill_name="api-skill",
            output_dir=tmp_path,
        )
        assert skill_path.exists()
        content = (skill_path / "SKILL.md").read_text()
        assert "Generated body" in content


# ── updater ───────────────────────────────────────────────────────────────────

class TestSkillUpdater:
    @patch("skill_manager.llm_client.LLMClient.detect_new_info")
    @patch("skill_manager.llm_client.LLMClient.rewrite_body")
    def test_update_applies_when_detected(self, mock_rewrite, mock_detect, skill_dir):
        mock_detect.return_value = {
            "should_update": True,
            "reason": "Found new API endpoint",
            "extracted_facts": ["New endpoint: POST /widgets"],
        }
        mock_rewrite.return_value = "## Overview\nUpdated body.\n\n## New\nPOST /widgets"

        from skill_manager.updater import SkillUpdater
        updater = SkillUpdater()
        result = updater.update_from_context(
            skill_path=skill_dir,
            context="We use POST /widgets to create widgets.",
        )
        assert result.updated is True
        assert result.backup_path is not None
        assert result.backup_path.exists()
        content = (skill_dir / "SKILL.md").read_text()
        assert "Updated body" in content

    @patch("skill_manager.llm_client.LLMClient.detect_new_info")
    def test_no_update_when_not_detected(self, mock_detect, skill_dir):
        mock_detect.return_value = {
            "should_update": False,
            "reason": "Nothing new",
            "extracted_facts": [],
        }
        from skill_manager.updater import SkillUpdater
        updater = SkillUpdater()
        result = updater.update_from_context(
            skill_path=skill_dir,
            context="Generic conversation with no new facts.",
        )
        assert result.updated is False
        assert not (skill_dir / ".backup_SKILL_").exists()

    @patch("skill_manager.llm_client.LLMClient.detect_new_info")
    @patch("skill_manager.llm_client.LLMClient.rewrite_body")
    def test_dry_run_does_not_write(self, mock_rewrite, mock_detect, skill_dir):
        mock_detect.return_value = {
            "should_update": True,
            "reason": "New info",
            "extracted_facts": ["fact"],
        }
        mock_rewrite.return_value = "## Changed\nSomething new."

        original = (skill_dir / "SKILL.md").read_text()

        from skill_manager.updater import SkillUpdater
        updater = SkillUpdater()
        result = updater.update_from_context(
            skill_path=skill_dir,
            context="Some context.",
            dry_run=True,
        )
        assert result.updated is True
        assert result.dry_run is True
        assert (skill_dir / "SKILL.md").read_text() == original

    def test_rollback(self, skill_dir):
        from skill_manager.updater import SkillUpdater
        from skill_manager.backup import BackupManager
        # Create a backup first
        BackupManager(skill_dir).create()
        # Modify the file
        (skill_dir / "SKILL.md").write_text("---\nname: test-skill\ndescription: Changed.\n---\nChanged body.")

        updater = SkillUpdater()
        ok = updater.rollback(skill_dir)
        assert ok
        content = (skill_dir / "SKILL.md").read_text()
        assert "Overview" in content


# ── scanner ───────────────────────────────────────────────────────────────────

class TestSkillScanner:
    def test_list_skills(self, skills_root):
        from skill_manager.scanner import SkillScanner
        scanner = SkillScanner(skills_dir=skills_root)
        skills = scanner.list_skills()
        names = {p.name for p in skills}
        assert "skill-alpha" in names
        assert "skill-beta" in names

    @patch("skill_manager.llm_client.LLMClient._json_call")
    def test_find_relevant_skills(self, mock_json, skills_root):
        mock_json.return_value = {"relevant_skills": ["skill-alpha"]}
        from skill_manager.scanner import SkillScanner
        scanner = SkillScanner(skills_dir=skills_root)
        relevant = scanner.find_relevant_skills("Some alpha-related context")
        assert any(p.name == "skill-alpha" for p in relevant)

    @patch("skill_manager.updater.SkillUpdater.update_from_context")
    @patch("skill_manager.llm_client.LLMClient._json_call")
    def test_scan_and_update(self, mock_json, mock_update, skills_root):
        from skill_manager.models import UpdateResult
        mock_json.return_value = {"relevant_skills": ["skill-alpha"]}
        mock_update.return_value = UpdateResult(
            skill_name="skill-alpha", updated=True, reason="Test update"
        )
        from skill_manager.scanner import SkillScanner
        scanner = SkillScanner(skills_dir=skills_root)
        results = scanner.scan_and_update(context="alpha context")
        assert len(results) == 1
        assert results[0].updated is True

    def test_report_formatting(self, skills_root):
        from skill_manager.models import UpdateResult
        from skill_manager.scanner import SkillScanner
        scanner = SkillScanner(skills_dir=skills_root)
        results = [
            UpdateResult("skill-alpha", True, "Added endpoint", extracted_facts=["fact1"]),
            UpdateResult("skill-beta", False, "Nothing new"),
        ]
        report = scanner.report(results)
        assert "Updated" in report
        assert "skill-alpha" in report
        assert "skill-beta" in report
        assert "fact1" in report
