"""Backup: hot-copy SQLite database + config into data/backup/<timestamp>/.

Keeps the newest ``DEFAULT_KEEP`` backup folders (override with ``--keep``) so a
daily schedule cannot fill the disk.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.platform.config import ROOT_DIR, settings

logger = logging.getLogger(__name__)

DEFAULT_KEEP = 14


def _prune(backup_root: Path, keep: int) -> list[str]:
    """Delete oldest timestamped backup folders beyond ``keep``."""
    if keep <= 0:
        return []
    folders = sorted(
        (path for path in backup_root.iterdir() if path.is_dir() and path.name[:8].isdigit()),
        key=lambda path: path.name,
    )
    removed = []
    for path in folders[:-keep]:
        shutil.rmtree(path, ignore_errors=True)
        removed.append(path.name)
    return removed


def backup(keep: int = DEFAULT_KEEP) -> Path:
    db_path = settings.data_dir / "epic.db"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = settings.data_dir / "backup" / stamp
    dest.mkdir(parents=True, exist_ok=True)

    if db_path.exists():
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(dest / "epic.db")
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        check = sqlite3.connect(dest / "epic.db")
        try:
            result = check.execute("PRAGMA integrity_check").fetchone()
            logger.info("integrity_check: %s", result[0] if result else "unknown")
        finally:
            check.close()

    config_file = ROOT_DIR / "config" / "default.yaml"
    if config_file.exists():
        shutil.copy2(config_file, dest / "default.yaml")

    removed = _prune(dest.parent, keep)
    if removed:
        logger.info("pruned %s old backup(s): %s", len(removed), ", ".join(removed))
    logger.info("backup written: %s", dest)
    return dest


def main() -> None:
    parser = argparse.ArgumentParser(description="EPIC database backup")
    parser.add_argument("--keep", type=int, default=DEFAULT_KEEP, help="backup folders to retain")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(f"backup written: {backup(keep=args.keep)}")


if __name__ == "__main__":
    main()
