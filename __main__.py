from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    package_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(package_dir.parent))
    __package__ = package_dir.name

from .audio_params import load_audio_params
from .common import ensure_dirs, is_admin, now, write_json
from .constants import MANIFEST_PATH, STATUS_PATH
from .console import (
    payload_success,
    print_inject_summary,
    print_params_summary,
    print_restore_summary,
    print_status_summary,
)
from .gme_config import install_configs, remove_local_av_config
from .hosts import install_hosts_block, remove_hosts_block
from .status import full_status


def require_admin() -> None:
    if not is_admin():
        raise SystemExit("需要管理员权限：请右键 PowerShell，选择“以管理员身份运行”，再重新执行。")


def run_inject_once() -> dict:
    profile = load_audio_params()
    config = install_configs()
    hosts = install_hosts_block()
    status = full_status()
    payload = {
        "time": now(),
        "action": "inject",
        "mode": "once",
        "attempt": 1,
        "audio_profile": profile,
        "config": config,
        "hosts": hosts,
        "status": status,
    }
    write_json(MANIFEST_PATH, payload)
    write_json(STATUS_PATH, status)
    return payload


def command_inject(args: argparse.Namespace) -> int:
    require_admin()
    ensure_dirs()
    payload = run_inject_once()
    print_inject_summary(payload)
    return 0 if payload_success(payload) else 2


def command_status(args: argparse.Namespace) -> int:
    load_audio_params()
    status = full_status()
    write_json(STATUS_PATH, status)
    print_status_summary(status)
    return 0 if status.get("effective") else 1


def command_params(args: argparse.Namespace) -> int:
    profile = load_audio_params()
    print_params_summary(profile)
    return 0


def command_restore(args: argparse.Namespace) -> int:
    require_admin()
    load_audio_params()
    hosts = remove_hosts_block()
    av = remove_local_av_config()
    status = full_status()
    payload = {"time": now(), "action": "restore", "hosts": hosts, "local_av_configs": av, "status": status}
    write_json(STATUS_PATH, status)
    print_restore_summary(payload)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="voice_param_helper", description="语音参数助手：应用、查看和恢复当前语音方案。")
    sub = parser.add_subparsers(dest="command")
    inject = sub.add_parser("inject", help="应用一次参数")
    inject.set_defaults(func=command_inject)
    status = sub.add_parser("status", help="查看是否已生效")
    status.set_defaults(func=command_status)
    params = sub.add_parser("params", help="查看当前方案")
    params.set_defaults(func=command_params)
    restore = sub.add_parser("restore", help="恢复本工具做过的修改")
    restore.set_defaults(func=command_restore)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        args = parser.parse_args(["inject"])
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
