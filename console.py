from __future__ import annotations

from .constants import AUDIO_PARAMS_PATH, SETTINGS_PATH, STATUS_PATH
from .paths import game_dir, gme_dir


RUNTIME_LABELS = {
    "matched": "游戏已使用当前方案",
    "matched_config_current": "游戏已使用当前方案",
    "not_matched": "游戏还未切换到当前方案",
    "stale_matched": "最近记录已匹配，进入语音场景后可再次确认",
    "stale_not_matched": "最近记录未匹配，请进入语音场景刷新",
    "no_sample": "还没有语音参数记录",
    "no_log": "还没有游戏语音记录",
}

PROCESSING_FIELDS = (
    ("回声消除", "aec"),
    ("自动音量", "agc"),
    ("普通降噪", "ans"),
    ("AI 降噪", "ains"),
    ("静音检测", "vad"),
    ("丢包保护", "fec"),
)


def println(text: str = "") -> None:
    print(text, flush=True)


def print_title(title: str) -> None:
    println(title)
    println("=" * 34)


def profile_label(info: dict) -> str:
    return str(info.get("name") or "自定义音频参数")


def runtime_label(runtime_status: str) -> str:
    return RUNTIME_LABELS.get(runtime_status, runtime_status)


def payload_success(payload: dict) -> bool:
    return bool(payload.get("config") and payload.get("hosts"))


def pick_value(data: dict, *keys: str) -> int | None:
    for key in keys:
        value = data.get(key)
        if value is not None:
            return value
    return None


def switch_text(value: int | None) -> str:
    if value is None:
        return "未知"
    if value == 0:
        return "关"
    if value == 1:
        return "开"
    return f"值 {value}"


def rate_text(value: int | None) -> str:
    if value is None:
        return "采样率未知"
    if value % 1000 == 0:
        return f"{value // 1000} kHz"
    return f"{value} Hz"


def bitrate_text(value: int | None) -> str:
    if value is None:
        return "码率未知"
    if value % 1000 == 0:
        return f"{value // 1000} kbps"
    return f"{value} bps"


def channel_text(value: int | None) -> str:
    if value == 1:
        return "单声道"
    if value == 2:
        return "双声道"
    if value is None:
        return "声道未知"
    return f"{value} 声道"


def audio_quality_text(audio: dict) -> str:
    return " / ".join(
        [
            rate_text(pick_value(audio, "sample_rate", "sr")),
            channel_text(pick_value(audio, "channel", "ch")),
            bitrate_text(pick_value(audio, "bitrate", "br")),
        ]
    )


def processing_text(audio: dict) -> str:
    values = [(label, pick_value(audio, key)) for label, key in PROCESSING_FIELDS]
    if values and all(value == 0 for _, value in values):
        return "音频处理已关闭，适合音乐或虚拟声卡输入"
    return "、".join(f"{label}{switch_text(value)}" for label, value in values)


def buffer_text(audio: dict) -> str:
    init = pick_value(audio, "jitter_init")
    minimum = pick_value(audio, "jitter_min")
    maximum = pick_value(audio, "jitter_max")
    if init is None and minimum is None and maximum is None:
        return "网络缓冲未知"
    init_text = "未知" if init is None else str(init)
    min_text = "未知" if minimum is None else str(minimum)
    max_text = "未知" if maximum is None else str(maximum)
    return f"初始 {init_text} ms，范围 {min_text}-{max_text} ms"


def print_profile_summary(profile: dict) -> None:
    target = profile.get("target") or {}
    println(f"方案：{profile_label(profile)}")
    description = profile.get("description")
    if description:
        println(f"用途：{description}")
    println(f"音质：{audio_quality_text(target)}")
    println(f"处理：{processing_text(target)}")
    println(f"网络缓冲：{buffer_text(target)}")


def format_mismatches(items: list[dict]) -> str:
    def value_text(value: object) -> str:
        return "未读取" if value is None else str(value)

    return "、".join(
        f"{item.get('name', '参数')}(目标 {value_text(item.get('expected'))}，当前 {value_text(item.get('actual'))})"
        for item in items
    )


def runtime_compare_lines(runtime: dict) -> list[str]:
    lines = []
    target = runtime.get("target_sample")
    if target:
        lines.append(f"游戏当前音质：{audio_quality_text(target)}")
        lines.append(f"游戏当前处理：{processing_text(target)}")
    mismatches = runtime.get("target_mismatches") or []
    if mismatches:
        lines.append(f"未匹配项：{format_mismatches(mismatches)}")
    if runtime.get("runtime_status") in {"stale_matched", "stale_not_matched"}:
        lines.append("说明：最近记录早于本次修改，请进入一次语音场景后再查看。")
    return lines


def next_step(runtime: dict, effective: bool) -> str:
    if effective:
        return "现在可以在游戏内测试语音或音乐输入。"
    if runtime.get("target_mismatches"):
        return "请重新进入一次游戏语音场景。"
    return "请启动游戏并进入一次语音场景，然后运行 status 查看是否生效。"


def print_inject_summary(payload: dict) -> None:
    profile = payload["audio_profile"]
    full = payload.get("status", {})
    runtime = full.get("runtime", {})
    diagnosis = full.get("diagnosis") or {}
    applied = payload_success(payload)
    effective = full.get("effective") is True
    print_title("语音参数助手")
    println(f"结果：{'配置已写入' if applied else '配置未完成'}")
    println(f"游戏记录：{'已确认生效' if effective else runtime_label(runtime.get('runtime_status', 'no_log'))}")
    print_profile_summary(profile)
    if diagnosis.get("message") and diagnosis.get("code") != "unknown":
        println(f"说明：{diagnosis['message']}")
    for line in runtime_compare_lines(runtime):
        println(line)
    println(f"下一步：{next_step(runtime, effective)}")
    println(f"状态文件：{STATUS_PATH}")


def print_status_summary(status: dict) -> None:
    runtime = status.get("runtime", {})
    hosts = status.get("hosts", {})
    profile = status.get("audio_profile") or {}
    diagnosis = status.get("diagnosis") or {}
    effective = bool(status.get("effective"))
    print_title("当前状态")
    println(f"状态：{'已生效' if effective else '待确认'}")
    if profile:
        print_profile_summary(profile)
    if diagnosis.get("message") and diagnosis.get("code") != "unknown":
        println(f"说明：{diagnosis['message']}")
    println(f"游戏记录：{runtime_label(runtime.get('runtime_status', 'no_log'))}")
    if runtime.get("target_sample_time"):
        println(f"记录时间：{runtime.get('target_sample_time')}")
    for line in runtime_compare_lines(runtime):
        println(line)
    maintenance = [
        "联网配置已锁定" if hosts.get("blocked") else "联网配置未锁定",
        "本地配置已写入" if status.get("configs_match_target") else "本地配置待确认",
    ]
    println(f"维护状态：{'；'.join(maintenance)}")
    if not effective:
        println(f"下一步：{next_step(runtime, False)}")
    println(f"状态文件：{STATUS_PATH}")


def print_path_summary() -> None:
    detected_game = game_dir()
    println(f"参数文件：{AUDIO_PARAMS_PATH}")
    println(f"设置文件：{SETTINGS_PATH}")
    println(f"语音数据目录：{gme_dir()}")
    println(f"游戏目录：{detected_game if detected_game else '未设置，当前也未检测到正在运行的游戏'}")


def print_params_summary(profile: dict) -> None:
    print_title("当前方案")
    print_profile_summary(profile)
    print_path_summary()


def print_restore_summary(payload: dict) -> None:
    hosts = payload.get("hosts", {})
    av_items = payload.get("local_av_configs", [])
    removed_count = sum(1 for item in av_items if item.get("removed"))
    print_title("恢复完成")
    println(f"联网配置：{'已恢复' if hosts.get('removed') else '无需恢复'}")
    println(f"本地语音配置：{'已移除 ' + str(removed_count) + ' 个文件' if removed_count else '无需移除'}")
    println("如需再次使用，请重新运行 inject。")
    println(f"状态文件：{STATUS_PATH}")
