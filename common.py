from __future__ import annotations

import ctypes
import json
from datetime import datetime
from pathlib import Path

from .constants import BACKUP_DIR, DATA_DIR


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def write_json(path: Path, payload: dict) -> None:
    ensure_dirs()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def backup_file(path: Path, tag: str) -> Path | None:
    if not path.exists():
        return None
    ensure_dirs()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup = BACKUP_DIR / f"{path.name}.{tag}.{stamp}.bak"
    counter = 1
    while backup.exists():
        backup = BACKUP_DIR / f"{path.name}.{tag}.{stamp}.{counter}.bak"
        counter += 1
    import shutil

    shutil.copy2(path, backup)
    return backup
