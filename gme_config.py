from __future__ import annotations

import json
import stat
from dataclasses import dataclass
from pathlib import Path

from .common import backup_file, ensure_dirs
from .constants import (
    SEQUENCE_FLOOR,
    TARGET_AUDIO,
)
from .paths import gme_dir, local_av_config_targets


@dataclass(frozen=True)
class AudioProfile:
    sample_rate: int
    kbps: int
    channel: int
    codec_prof: int
    frame: int
    au_scheme: int
    max_antishake_max: int
    max_antishake_min: int
    min_antishake: int


PROFILE_AU_SCHEMES = {
    1: 5,
    2: 6,
    3: 7,
    4: 5,
    5: 5,
    6: 7,
}


def transform_byte(value: int) -> int:
    cl = value & 0xFF
    dl = cl
    if dl & 0x80:
        dl = ((dl | ~0xFF) >> 2) & 0xFF
    else:
        dl = (dl >> 2) & 0xFF
    al = (cl << 2) & 0xFF
    dl = (dl ^ al) & 0xFF
    dl &= 0x33
    cl = (cl << 2) & 0xFF
    return (dl ^ cl) & 0xFF


def transform(data: bytes) -> bytes:
    return bytes(transform_byte(byte) for byte in data)


def make_writable(path: Path) -> None:
    if path.exists():
        path.chmod(path.stat().st_mode | stat.S_IWRITE)


def make_readonly(path: Path) -> None:
    if path.exists():
        path.chmod(path.stat().st_mode & ~stat.S_IWRITE)


def load_encoded_config(path: Path) -> dict:
    return json.loads(transform(path.read_bytes()).decode("utf-8"))


def dump_encoded_config(config: dict) -> bytes:
    raw = json.dumps(config, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return transform(raw)


def iter_profiles(config: dict) -> list[dict]:
    conf = config.get("data", {}).get("conf", {})
    if isinstance(conf, dict):
        return [item for item in conf.values() if isinstance(item, dict)]
    if isinstance(conf, list):
        return [item for item in conf if isinstance(item, dict)]
    return []


def profile_target(profile_type: int | None) -> AudioProfile | None:
    au_scheme = PROFILE_AU_SCHEMES.get(profile_type)
    if au_scheme is None:
        return None
    return AudioProfile(
        TARGET_AUDIO["sample_rate"],
        TARGET_AUDIO["kbps"],
        TARGET_AUDIO["channel"],
        TARGET_AUDIO["codec_prof"],
        TARGET_AUDIO["frame"],
        au_scheme,
        TARGET_AUDIO["jitter_max"],
        TARGET_AUDIO["jitter_min"],
        TARGET_AUDIO["jitter_init"],
    )


def patch_profile(item: dict) -> None:
    profile_type = item.get("type")
    target = profile_target(profile_type)
    audio = item.setdefault("audio", {})
    if target:
        audio["sample_rate"] = target.sample_rate
        audio["kbps"] = target.kbps
        audio["channel"] = target.channel
        audio["codec_prof"] = target.codec_prof
        audio["frame"] = target.frame
        audio["au_scheme"] = target.au_scheme
        audio["max_antishake_max"] = target.max_antishake_max
        audio["max_antishake_min"] = target.max_antishake_min
        audio["min_antishake"] = target.min_antishake
    audio["aec"] = TARGET_AUDIO["aec"]
    audio["agc"] = TARGET_AUDIO["agc"]
    audio["ans"] = TARGET_AUDIO["ans"]
    audio["ains"] = TARGET_AUDIO["ains"]
    audio["vad"] = TARGET_AUDIO["vad"]
    audio["anti_dropout"] = TARGET_AUDIO["fec"]
    audio["silence_detect"] = 0
    if profile_type == 1:
        item["is_default"] = 1
    elif profile_type == 5:
        item["is_default"] = 0


def summarize_config(config: dict) -> list[dict]:
    rows = []
    for item in iter_profiles(config):
        audio = item.get("audio", {})
        rows.append(
            {
                "type": item.get("type"),
                "role": item.get("role"),
                "default": item.get("is_default"),
                "sr": audio.get("sample_rate"),
                "kbps": audio.get("kbps"),
                "ch": audio.get("channel"),
                "codec": audio.get("codec_prof"),
                "frame": audio.get("frame"),
                "aec": audio.get("aec"),
                "agc": audio.get("agc"),
                "ans": audio.get("ans"),
                "ains": audio.get("ains"),
                "vad": audio.get("vad"),
                "fec": audio.get("anti_dropout"),
                "silence": audio.get("silence_detect"),
                "jitter_init": audio.get("min_antishake"),
                "jitter_min": audio.get("max_antishake_min"),
                "jitter_max": audio.get("max_antishake_max"),
            }
        )
    return rows


def patch_config(config: dict) -> None:
    data = config.setdefault("data", {})
    old_sequence = data.get("sequence", 0)
    if not isinstance(old_sequence, int) or old_sequence < SEQUENCE_FLOOR:
        data["sequence"] = SEQUENCE_FLOOR
    for item in iter_profiles(config):
        patch_profile(item)


def patch_control_configs() -> list[dict]:
    base = gme_dir()
    if not base.exists():
        return []
    results = []
    for path in sorted(base.glob("gmesdk_control_*.config")):
        config = load_encoded_config(path)
        before = summarize_config(config)
        patch_config(config)
        patched = dump_encoded_config(config)
        changed = path.read_bytes() != patched
        before_backup = backup_file(path, "control") if changed else None
        if changed:
            make_writable(path)
            try:
                path.write_bytes(patched)
            finally:
                make_readonly(path)
        else:
            make_readonly(path)
        after = summarize_config(load_encoded_config(path))
        results.append(
            {
                "path": str(path),
                "backup": str(before_backup) if before_backup else None,
                "changed": changed,
                "before": before,
                "after": after,
                "readonly": not bool(path.stat().st_mode & stat.S_IWRITE),
            }
        )
    return results


def source_config() -> dict:
    base = gme_dir()
    configs = sorted(base.glob("gmesdk_control_*.config")) if base.exists() else []
    if configs:
        config = load_encoded_config(configs[0])
        patch_config(config)
        return config
    config = {
        "data": {
            "scheme": 3,
            "sequence": SEQUENCE_FLOOR,
            "conf": {
                "1": {
                    "type": 1,
                    "role": "esports",
                    "is_default": 1,
                    "audio": {
                        "aec": TARGET_AUDIO["aec"],
                        "agc": TARGET_AUDIO["agc"],
                        "ans": TARGET_AUDIO["ans"],
                        "ains": TARGET_AUDIO["ains"],
                        "vad": TARGET_AUDIO["vad"],
                        "anti_dropout": TARGET_AUDIO["fec"],
                        "au_scheme": 5,
                        "channel": TARGET_AUDIO["channel"],
                        "codec_prof": TARGET_AUDIO["codec_prof"],
                        "frame": TARGET_AUDIO["frame"],
                        "kbps": TARGET_AUDIO["kbps"],
                        "max_antishake_max": TARGET_AUDIO["jitter_max"],
                        "max_antishake_min": TARGET_AUDIO["jitter_min"],
                        "min_antishake": TARGET_AUDIO["jitter_init"],
                        "sample_rate": TARGET_AUDIO["sample_rate"],
                        "silence_detect": 0,
                    },
                    "net": {
                        "rc_anti_dropout": TARGET_AUDIO["fec"],
                        "rc_init_delay": TARGET_AUDIO["jitter_init"],
                        "rc_max_delay": TARGET_AUDIO["jitter_max"],
                    },
                }
            },
        }
    }
    return config


def install_local_av_config() -> list[dict]:
    payload = json.dumps(source_config(), ensure_ascii=False, indent=2)
    results = []
    for path in local_av_config_targets():
        path.parent.mkdir(parents=True, exist_ok=True)
        current = path.read_text(encoding="utf-8", errors="replace") if path.exists() else None
        changed = current != payload
        backup = backup_file(path, "av_config") if changed else None
        if changed:
            make_writable(path)
            path.write_text(payload, encoding="utf-8")
        make_readonly(path)
        results.append(
            {
                "path": str(path),
                "backup": str(backup) if backup else None,
                "changed": changed,
                "size": path.stat().st_size,
                "readonly": not bool(path.stat().st_mode & stat.S_IWRITE),
            }
        )
    return results


def remove_local_av_config() -> list[dict]:
    results = []
    for path in local_av_config_targets():
        existed = path.exists()
        if existed:
            make_writable(path)
            path.unlink()
        results.append({"path": str(path), "removed": existed})
    return results


def install_configs() -> dict:
    ensure_dirs()
    control = patch_control_configs()
    av_config = install_local_av_config()
    return {"control": control, "av_config": av_config}
