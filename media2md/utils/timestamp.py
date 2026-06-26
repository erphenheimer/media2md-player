"""时间戳工具函数。"""


def ms_to_srt_time(ms: int) -> str:
    """将毫秒转换为 SRT 时间戳格式: HH:MM:SS,mmm"""
    h, remainder = divmod(ms, 3600000)
    m, remainder = divmod(remainder, 60000)
    s, ms_part = divmod(remainder, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms_part:03d}"


def ms_to_markdown_time(ms: int) -> str:
    """将毫秒转换为 Markdown 友好格式: HH:MM:SS.mmm"""
    h, remainder = divmod(ms, 3600000)
    m, remainder = divmod(remainder, 60000)
    s, ms_part = divmod(remainder, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms_part:03d}"


def parse_srt_timestamp(ts: str) -> int:
    """将 SRT 时间戳解析为毫秒。格式: HH:MM:SS,mmm"""
    # 支持逗号和点号分隔
    ts_clean = ts.replace(",", ".")
    parts = ts_clean.split(":")
    if len(parts) == 3:
        h, m, s_ms = parts
        s, ms = s_ms.split(".")
        return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms)
    return 0
