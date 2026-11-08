"""Backup: hot-copy SQLite database + config into data/backup/<timestamp>/."""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from app.platform.config import ROOT_DIR, settings


def backup() -> Path:
    db_path = settings.data_dir / "epic.db"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
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

    config_file = ROOT_DIR / "config" / "default.yaml"
    if config_file.exists():
        shutil.copy2(config_file, dest / "default.yaml")

    print(f"backup written: {dest}")
    return dest


if __name__ == "__main__":
    backup()
