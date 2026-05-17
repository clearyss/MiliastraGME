from __future__ import annotations

import os
from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent
DATA_DIR = PACKAGE_DIR / "data"
BACKUP_DIR = PACKAGE_DIR / "backups"
AUDIO_PARAMS_PATH = PACKAGE_DIR / "audio_params.json"
SETTINGS_PATH = PACKAGE_DIR / "settings.json"
STATUS_PATH = DATA_DIR / "gme_voice_auto_injector_status.json"
MANIFEST_PATH = DATA_DIR / "gme_voice_auto_injector_manifest.json"
HOSTS_PATH = Path(os.environ.get("SystemRoot", r"C:\Windows")) / r"System32\drivers\etc\hosts"
HOSTS_BEGIN = "# BEGIN GME_VOICE_AUTO_INJECTOR"
HOSTS_END = "# END GME_VOICE_AUTO_INJECTOR"
BLOCKED_HOSTS = ["gmeconf.qcloud.com", "gmeosconf.qcloud.com"]
SEQUENCE_FLOOR = 2_147_483_647
TARGET_AUDIO: dict[str, int] = {}
