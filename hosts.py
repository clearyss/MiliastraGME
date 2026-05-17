from __future__ import annotations

import subprocess

from .common import backup_file
from .constants import BLOCKED_HOSTS, HOSTS_BEGIN, HOSTS_END, HOSTS_PATH

LEGACY_BEGIN = "# BEGIN GME_REMOTE_CONTROL_CONFIG_BLOCK"
LEGACY_END = "# END GME_REMOTE_CONTROL_CONFIG_BLOCK"


def read_hosts() -> str:
    return HOSTS_PATH.read_text(encoding="utf-8", errors="replace")


def remove_block_text(text: str) -> str:
    result = []
    skipping = False
    for line in text.splitlines():
        if line.strip() in {HOSTS_BEGIN, LEGACY_BEGIN}:
            skipping = True
            continue
        if line.strip() in {HOSTS_END, LEGACY_END}:
            skipping = False
            continue
        if not skipping:
            result.append(line)
    return "\n".join(result).rstrip() + "\n"


def block_text() -> str:
    lines = [HOSTS_BEGIN]
    for host in BLOCKED_HOSTS:
        lines.append(f"0.0.0.0 {host}")
        lines.append(f"::1 {host}")
    lines.append(HOSTS_END)
    return "\n".join(lines) + "\n"


def flush_dns() -> None:
    subprocess.run(["ipconfig", "/flushdns"], check=False, capture_output=True, text=True)


def install_hosts_block() -> dict:
    current = read_hosts()
    patched = remove_block_text(current) + "\n" + block_text()
    changed = current != patched
    backup = backup_file(HOSTS_PATH, "hosts") if changed else None
    if changed:
        HOSTS_PATH.write_text(patched, encoding="utf-8")
        flush_dns()
    return {"path": str(HOSTS_PATH), "backup": str(backup) if backup else None, "changed": changed, "blocked": BLOCKED_HOSTS}


def remove_hosts_block() -> dict:
    existed = HOSTS_BEGIN in read_hosts()
    if existed:
        HOSTS_PATH.write_text(remove_block_text(read_hosts()), encoding="utf-8")
        flush_dns()
    return {"path": str(HOSTS_PATH), "removed": existed}


def hosts_status() -> dict:
    text = read_hosts()
    lines = [line.strip().lower() for line in text.splitlines()]
    blocked = all(
        f"0.0.0.0 {host}".lower() in lines or f"::1 {host}".lower() in lines
        for host in BLOCKED_HOSTS
    )
    return {"path": str(HOSTS_PATH), "blocked": blocked, "hosts": BLOCKED_HOSTS}
