from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from .constants import SETTINGS_PATH


DEFAULT_SETTINGS = {
    "process_name": "YuanShen.exe",
    "module_name": "gmesdk.dll",
    "gme_dir": "",
    "game_dir": "",
}


def load_settings() -> dict[str, str]:
    if not SETTINGS_PATH.exists():
        SETTINGS_PATH.write_text(json.dumps(DEFAULT_SETTINGS, ensure_ascii=False, indent=2), encoding="utf-8")
    data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8", errors="replace"))
    if not isinstance(data, dict):
        raise ValueError(f"配置文件格式错误：{SETTINGS_PATH}")
    result = DEFAULT_SETTINGS.copy()
    for key in result:
        value = data.get(key, result[key])
        if not isinstance(value, str):
            raise ValueError(f"settings.json 中 {key} 必须是字符串")
        result[key] = value.strip()
    return result


def process_name() -> str:
    return load_settings()["process_name"] or DEFAULT_SETTINGS["process_name"]


def module_name() -> str:
    return load_settings()["module_name"] or DEFAULT_SETTINGS["module_name"]


def appdata_dir() -> Path:
    return Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))


def gme_dir() -> Path:
    configured = load_settings()["gme_dir"]
    return Path(configured).expanduser() if configured else appdata_dir() / "GME" / process_name()


def detect_game_dir_from_process() -> Path | None:
    name = process_name().replace("'", "''")
    script = (
        f"$p = Get-CimInstance Win32_Process -Filter \"Name='{name}'\" -ErrorAction SilentlyContinue | "
        "Select-Object -First 1 -ExpandProperty ExecutablePath; if ($p) { $p }"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    value = result.stdout.strip().splitlines()
    if not value:
        return None
    path = Path(value[0]).expanduser()
    return path.parent if path.exists() else None


def game_dir() -> Path | None:
    configured = load_settings()["game_dir"]
    if configured:
        return Path(configured).expanduser()
    return detect_game_dir_from_process()


def local_av_config_targets() -> list[Path]:
    targets = [gme_dir() / "av_config.json"]
    game = game_dir()
    if game:
        targets.extend(
            [
                game / "av_config.json",
                game / "YuanShen_Data" / "Plugins" / "av_config.json",
            ]
        )
    return targets
