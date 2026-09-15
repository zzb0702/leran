from __future__ import annotations

from ..models import Segment


def _ts(ms: int) -> str:
    ms = max(0, int(ms))
    h = ms // 3_600_000
    m = (ms % 3_600_000) // 60_000
    s = (ms % 60_000) // 1000
    milli = ms % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{milli:03d}"


def segments_to_srt(segments: list[Segment], lang: str = "bilingual") -> str:
    lines: list[str] = []
    for i, seg in enumerate(segments, start=1):
        en = seg.text_en
        zh = seg.text_zh
        if lang == "en":
            body = en
        elif lang == "zh":
            body = zh
        else:
            body = f"{en}\n{zh}" if zh else en
        lines.append(f"{i}\n{_ts(seg.start_ms)} --> {_ts(seg.end_ms)}\n{body}\n")
    return "\n".join(lines)


def segments_to_vtt(segments: list[Segment], lang: str = "bilingual") -> str:
    parts = ["WEBVTT\n"]
    for seg in segments:
        en = seg.text_en
        zh = seg.text_zh
        if lang == "en":
            body = en
        elif lang == "zh":
            body = zh
        else:
            body = f"{en}\n{zh}" if zh else en
        start = _ts(seg.start_ms).replace(",", ".")
        end = _ts(seg.end_ms).replace(",", ".")
        parts.append(f"{start} --> {end}\n{body}\n")
    return "\n".join(parts)
