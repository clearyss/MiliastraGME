from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from .constants import TARGET_AUDIO
from .gme_config import load_encoded_config, summarize_config
from .hosts import hosts_status
from .paths import gme_dir, local_av_config_targets
from .audio_params import active_audio_info, target_audio_snapshot


AUD_PARAM_RE = re.compile(
    r"AudParam\. Aec:(?P<aec>\d+), Agc:(?P<agc>\d+), Ans:(?P<ans>\d+), AiNs:(?P<ains>\d+) "
    r"Vad:(?P<vad>\d+), Fec:(?P<fec>\d+), Frame:(?P<frame>\d+), SR:(?P<sr>\d+), "
    r"CH:(?P<ch>\d+), Codec:(?P<codec>\d+), BR:(?P<br>\d+), "
    r"Jitter:(?P<jitter_init>\d+),(?P<jitter_min>\d+)-(?P<jitter_max>\d+)"
)
SET_PARAM_RE = re.compile(
    r"codetype:(?P<codec>\d+) (?P<sr>\d+) (?P<ch>\d+) (?P<br>\d+) (?P<frame>\d+) "
    r"DTX:(?P<dtx>\d+) VAD:(?P<vad>\d+) AEC:(?P<aec>\d+) NS:(?P<ans>\d+) "
    r"AINS:(?P<ains>\d+) AGC:(?P<agc>\d+)"
)
AV_CONTROL_RE = re.compile(r"AVControlConfig (?P<event>json string|invalid json string|error|http response ok)")
LOG_TIME_RE = re.compile(r"^(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})\.(?P<millisecond>\d{3})")
COMPARE_FIELDS = (
    ("回声消除", "aec", "aec", "eq"),
    ("自动音量", "agc", "agc", "eq"),
    ("普通降噪", "ans", "ans", "eq"),
    ("AI 降噪", "ains", "ains", "eq"),
    ("静音检测", "vad", "vad", "eq"),
    ("丢包保护", "fec", "fec", "eq"),
    ("帧长", "frame", "frame", "eq"),
    ("采样率", "sample_rate", "sr", "eq"),
    ("声道", "channel", "ch", "eq"),
    ("编码模式", "codec_prof", "codec", "eq"),
    ("码率", "bitrate", "br", "min"),
    ("缓冲初始值", "jitter_init", "jitter_init", "eq"),
    ("缓冲下限", "jitter_min", "jitter_min", "eq"),
    ("缓冲上限", "jitter_max", "jitter_max", "eq"),
)


def parse_values(match: re.Match[str]) -> dict[str, int]:
    return {key: int(value) for key, value in match.groupdict().items()}


def latest_log() -> Path | None:
    base = gme_dir()
    logs = sorted(base.glob("GMESDK_*.log"), key=lambda item: item.stat().st_mtime, reverse=True) if base.exists() else []
    return logs[0] if logs else None


def log_date(log: Path) -> datetime | None:
    match = re.search(r"GMESDK_(\d{8})\.log$", log.name)
    if not match:
        return None
    return datetime.strptime(match.group(1), "%Y%m%d")


def item_time(log: Path, item: dict | None) -> str | None:
    if not item:
        return None
    base = log_date(log)
    match = LOG_TIME_RE.search(item.get("raw", ""))
    if not base or not match:
        return None
    value = base.replace(
        hour=int(match.group("hour")),
        minute=int(match.group("minute")),
        second=int(match.group("second")),
        microsecond=int(match.group("millisecond")) * 1000,
    )
    return value.isoformat(timespec="milliseconds")


def item_timestamp(log: Path, item: dict | None) -> float | None:
    value = item_time(log, item)
    if not value:
        return None
    return datetime.fromisoformat(value).timestamp()


def latest_config_mtime() -> float | None:
    paths = []
    base = gme_dir()
    if base.exists():
        paths.extend(base.glob("gmesdk_control_*.config"))
    paths.extend(path for path in local_av_config_targets() if path.exists())
    if not paths:
        return None
    return max(path.stat().st_mtime for path in paths)


def matches_target(item: dict | None) -> bool | None:
    if not item:
        return None
    return (
        item.get("aec") == TARGET_AUDIO["aec"]
        and item.get("agc") == TARGET_AUDIO["agc"]
        and item.get("ans") == TARGET_AUDIO["ans"]
        and item.get("ains") == TARGET_AUDIO["ains"]
        and item.get("vad") == TARGET_AUDIO["vad"]
        and item.get("fec", TARGET_AUDIO["fec"]) == TARGET_AUDIO["fec"]
        and item.get("frame", TARGET_AUDIO["frame"]) == TARGET_AUDIO["frame"]
        and item.get("sr") == TARGET_AUDIO["sample_rate"]
        and item.get("ch") == TARGET_AUDIO["channel"]
        and item.get("codec") == TARGET_AUDIO["codec_prof"]
        and item.get("br", 0) >= TARGET_AUDIO["bitrate"]
        and item.get("jitter_init", TARGET_AUDIO["jitter_init"]) == TARGET_AUDIO["jitter_init"]
        and item.get("jitter_min", TARGET_AUDIO["jitter_min"]) == TARGET_AUDIO["jitter_min"]
        and item.get("jitter_max", TARGET_AUDIO["jitter_max"]) == TARGET_AUDIO["jitter_max"]
    )


def target_mismatches(item: dict | None) -> list[dict]:
    if not item:
        return []
    result = []
    for label, target_key, sample_key, mode in COMPARE_FIELDS:
        expected = TARGET_AUDIO[target_key]
        actual = item.get(sample_key)
        ok = actual >= expected if mode == "min" and actual is not None else actual == expected
        if not ok:
            result.append({"name": label, "expected": expected, "actual": actual})
    return result


def runtime_log_status() -> dict:
    log = latest_log()
    if not log:
        return {"log": None, "runtime_status": "no_log"}
    aud_params = []
    set_params = []
    av_events = []
    with log.open("r", encoding="utf-8", errors="replace") as file:
        for line_number, line in enumerate(file, 1):
            aud = AUD_PARAM_RE.search(line)
            if aud:
                item = parse_values(aud)
                item["line"] = line_number
                item["raw"] = line.strip()
                aud_params.append(item)
            set_param = SET_PARAM_RE.search(line)
            if set_param:
                item = parse_values(set_param)
                item["line"] = line_number
                item["raw"] = line.strip()
                set_params.append(item)
            av = AV_CONTROL_RE.search(line)
            if av:
                av_events.append({"event": av.group("event"), "line": line_number, "raw": line.strip()})
    latest = None
    target_sample = aud_params[-1] if aud_params else None
    candidates = []
    if aud_params:
        candidates.append(aud_params[-1])
    if set_params:
        candidates.append(set_params[-1])
    if candidates:
        latest = max(candidates, key=lambda item: item["line"])
    config_mtime = latest_config_mtime()
    target_timestamp = item_timestamp(log, target_sample)
    verification_valid = bool(
        target_timestamp is not None and config_mtime is not None and target_timestamp >= config_mtime
    )
    sample_matches = matches_target(target_sample)
    matched = sample_matches if verification_valid else None
    mismatches = target_mismatches(target_sample)
    if not target_sample:
        runtime_status = "no_sample"
    elif verification_valid:
        runtime_status = "matched" if matched else "not_matched"
    else:
        runtime_status = "stale_matched" if sample_matches else "stale_not_matched"
    return {
        "log": str(log),
        "log_last_write": datetime.fromtimestamp(log.stat().st_mtime).isoformat(timespec="seconds"),
        "latest_aud_param": aud_params[-1] if aud_params else None,
        "latest_set_aud_param": set_params[-1] if set_params else None,
        "latest_runtime_sample": latest,
        "latest_runtime_sample_time": item_time(log, latest),
        "target_sample": target_sample,
        "target_sample_time": item_time(log, target_sample),
        "latest_config_time": datetime.fromtimestamp(config_mtime).isoformat(timespec="seconds") if config_mtime else None,
        "verification_valid": verification_valid,
        "latest_av_control_event": av_events[-1] if av_events else None,
        "expected": target_audio_snapshot(),
        "target_mismatches": mismatches,
        "sample_matches_target": sample_matches,
        "matches_target": matched,
        "runtime_status": runtime_status,
    }


def config_status() -> dict:
    controls = []
    base = gme_dir()
    if base.exists():
        for path in sorted(base.glob("gmesdk_control_*.config")):
            try:
                summary = summarize_config(load_encoded_config(path))
            except Exception as exc:
                summary = [{"error": str(exc)}]
            controls.append({"path": str(path), "readonly": bool(path.stat().st_file_attributes & 1), "summary": summary})
    av_configs = []
    for path in local_av_config_targets():
        summary = []
        if path.exists():
            try:
                summary = summarize_config(json.loads(path.read_text(encoding="utf-8", errors="replace")))
            except Exception as exc:
                summary = [{"error": str(exc)}]
        av_configs.append(
            {
                "path": str(path),
                "exists": path.exists(),
                "readonly": path.exists() and bool(path.stat().st_file_attributes & 1),
                "summary": summary,
            }
        )
    return {"control_configs": controls, "local_av_configs": av_configs}


def summary_matches_target(row: dict) -> bool:
    return (
        row.get("sr") == TARGET_AUDIO["sample_rate"]
        and row.get("kbps") == TARGET_AUDIO["kbps"]
        and row.get("ch") == TARGET_AUDIO["channel"]
        and row.get("codec") == TARGET_AUDIO["codec_prof"]
        and row.get("frame", TARGET_AUDIO["frame"]) == TARGET_AUDIO["frame"]
        and row.get("aec") == TARGET_AUDIO["aec"]
        and row.get("agc") == TARGET_AUDIO["agc"]
        and row.get("ans") == TARGET_AUDIO["ans"]
        and row.get("ains") == TARGET_AUDIO["ains"]
        and row.get("vad") == TARGET_AUDIO["vad"]
        and row.get("fec", TARGET_AUDIO["fec"]) == TARGET_AUDIO["fec"]
        and row.get("jitter_init", TARGET_AUDIO["jitter_init"]) == TARGET_AUDIO["jitter_init"]
        and row.get("jitter_min", TARGET_AUDIO["jitter_min"]) == TARGET_AUDIO["jitter_min"]
        and row.get("jitter_max", TARGET_AUDIO["jitter_max"]) == TARGET_AUDIO["jitter_max"]
    )


def configs_match_target(configs: dict) -> bool:
    rows = []
    for item in configs.get("control_configs", []):
        rows.extend(row for row in item.get("summary", []) if "error" not in row)
    for item in configs.get("local_av_configs", []):
        rows.extend(row for row in item.get("summary", []) if "error" not in row)
    return bool(rows) and all(summary_matches_target(row) for row in rows)


def diagnose_status(runtime: dict, configs_matched: bool) -> dict:
    mismatches = runtime.get("target_mismatches") or []
    if runtime.get("matches_target") is True:
        return {"code": "matched", "message": "游戏当前使用的语音参数已是目标方案。"}
    if mismatches and configs_matched:
        fields = "、".join(item["name"] for item in mismatches)
        return {
            "code": "runtime_override",
            "message": f"配置已写入，但游戏当前仍使用自己的数值：{fields}。",
            "fields": mismatches,
        }
    if mismatches:
        fields = "、".join(item["name"] for item in mismatches)
        return {
            "code": "runtime_mismatch",
            "message": f"游戏当前语音参数还未切换到目标方案：{fields}。",
            "fields": mismatches,
        }
    if runtime.get("runtime_status") in {"stale_matched", "stale_not_matched"}:
        return {"code": "stale_log", "message": "最近记录早于本次修改，请进入一次语音场景让游戏刷新。"}
    return {"code": "unknown", "message": "还没有足够的游戏记录可确认结果。"}


def full_status() -> dict:
    runtime = runtime_log_status()
    configs = config_status()
    configs_matched = configs_match_target(configs)
    effective = runtime.get("matches_target") is True or (
        runtime.get("sample_matches_target") is True and configs_matched
    )
    if runtime.get("matches_target") is not True and runtime.get("sample_matches_target") is True and configs_matched:
        runtime = dict(runtime)
        runtime["runtime_status"] = "matched_config_current"
    diagnosis = diagnose_status(runtime, configs_matched)
    return {
        "time": datetime.now().isoformat(timespec="seconds"),
        "audio_profile": active_audio_info(),
        "effective": effective,
        "configs_match_target": configs_matched,
        "diagnosis": diagnosis,
        "runtime": runtime,
        "hosts": hosts_status(),
        "configs": configs,
    }
