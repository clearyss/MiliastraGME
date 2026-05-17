from __future__ import annotations

import json
from typing import Any

from .constants import AUDIO_PARAMS_PATH, TARGET_AUDIO


PARAM_KEYS = (
    "aec",
    "agc",
    "ans",
    "ains",
    "vad",
    "fec",
    "frame",
    "sample_rate",
    "channel",
    "codec_prof",
    "kbps",
    "bitrate",
    "jitter_init",
    "jitter_min",
    "jitter_max",
)


class AudioParamError(ValueError):
    pass


def read_params_file() -> dict[str, Any]:
    if not AUDIO_PARAMS_PATH.exists():
        raise AudioParamError(f"未找到参数文件：{AUDIO_PARAMS_PATH}")
    data = json.loads(AUDIO_PARAMS_PATH.read_text(encoding="utf-8", errors="replace"))
    if not isinstance(data, dict):
        raise AudioParamError(f"参数文件格式错误：{AUDIO_PARAMS_PATH}")
    return data


def validate_audio(data: dict[str, Any]) -> dict[str, int]:
    audio = data.get("audio", data)
    if not isinstance(audio, dict):
        raise AudioParamError("audio_params.json 中 audio 必须是对象")
    result = {}
    for key in PARAM_KEYS:
        if key not in audio:
            raise AudioParamError(f"audio_params.json 缺少参数：{key}")
        value = audio[key]
        if not isinstance(value, int):
            raise AudioParamError(f"audio_params.json 参数 {key} 必须是整数")
        if value < 0:
            raise AudioParamError(f"audio_params.json 参数 {key} 不能为负数")
        result[key] = value
    if result["bitrate"] < result["kbps"] * 1000:
        raise AudioParamError("bitrate 不应小于 kbps * 1000")
    return result


def load_audio_params() -> dict[str, Any]:
    data = read_params_file()
    audio = validate_audio(data)
    TARGET_AUDIO.clear()
    TARGET_AUDIO.update(audio)
    return active_audio_info(data)


def active_audio_info(data: dict[str, Any] | None = None) -> dict[str, Any]:
    source = read_params_file() if data is None else data
    audio = validate_audio(source)
    return {
        "name": str(source.get("name") or "自定义音频参数"),
        "description": str(source.get("description") or "用户自定义参数"),
        "path": str(AUDIO_PARAMS_PATH),
        "target": audio,
        "signature": target_signature(audio),
        "target_text": format_target(audio),
    }


def target_audio_snapshot(audio: dict[str, int] | None = None) -> dict[str, int]:
    source = TARGET_AUDIO if audio is None else audio
    return {key: int(source[key]) for key in PARAM_KEYS}


def target_signature(audio: dict[str, int] | None = None) -> str:
    return json.dumps(target_audio_snapshot(audio), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def format_target(audio: dict[str, int] | None = None) -> str:
    target = target_audio_snapshot(audio)
    return (
        f"AEC={target['aec']}，AGC={target['agc']}，ANS={target['ans']}，AINS={target['ains']}，"
        f"VAD={target['vad']}，FEC={target['fec']}，Frame={target['frame']}，"
        f"SR={target['sample_rate']}，CH={target['channel']}，Codec={target['codec_prof']}，"
        f"BR={target['bitrate']}，Jitter={target['jitter_init']},{target['jitter_min']}-{target['jitter_max']}"
    )
