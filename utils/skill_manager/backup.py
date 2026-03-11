"""
Backup manager - creates/restores timestamped SKILL.md backups
"""

import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

BACKUP_PREFIX = ".backup_SKILL_"
BACKUP_GLOB = f"{BACKUP_PREFIX}*.md"


class BackupManager:
    def __init__(self, skill_path: Path, max_backups: int = 10):
        self.skill_path = skill_path
        self.max_backups = max_backups

    def create(self) -> Optional[Path]:
        """Create a timestamped backup of SKILL.md. Returns backup path."""
        src = self.skill_path / "SKILL.md"
        if not src.exists():
            return None

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = self.skill_path / f"{BACKUP_PREFIX}{ts}.md"
        shutil.copy2(src, dst)
        logger.debug(f"Backup created: {dst.name}")
        self._prune()
        return dst

    def rollback(self, steps: int = 1) -> bool:
        """Restore the Nth most recent backup (default: latest)."""
        backups = self._sorted_backups()
        if not backups:
            logger.error("No backups available to rollback")
            return False

        idx = min(steps - 1, len(backups) - 1)
        target = backups[idx]
        shutil.copy2(target, self.skill_path / "SKILL.md")
        logger.info(f"Rolled back to: {target.name}")
        return True

    def list_backups(self) -> list[Path]:
        return self._sorted_backups()

    def _sorted_backups(self) -> list[Path]:
        return sorted(self.skill_path.glob(BACKUP_GLOB), reverse=True)

    def _prune(self):
        for old in self._sorted_backups()[self.max_backups:]:
            old.unlink()
            logger.debug(f"Pruned old backup: {old.name}")
