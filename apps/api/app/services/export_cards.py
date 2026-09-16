from __future__ import annotations

import csv
import io
import shutil
import subprocess
import zipfile
from pathlib import Path

from ..config import settings
from ..models import Card, Media


def ffmpeg_bin() -> str | None:
    if settings.ffmpeg_path:
        p = Path(settings.ffmpeg_path)
        if p.exists():
            return str(p)
    return shutil.which("ffmpeg")


def extract_audio_clip(
    media: Media,
    start_ms: int,
    end_ms: int,
    *,
    pad_ms: int = 200,
    max_ms: int = 6000,
) -> Path | None:
    """Cut a short mp3 clip around the card timestamp. Returns path or None if ffmpeg missing."""
    ffmpeg = ffmpeg_bin()
    if not ffmpeg:
        return None
    src = settings.media_dir / media.storage_key
    if not src.exists():
        return None

    start = max(0, start_ms - pad_ms)
    duration = min(max_ms, max(400, (end_ms - start_ms) + pad_ms * 2))
    settings.clip_dir.mkdir(parents=True, exist_ok=True)
    out = settings.clip_dir / f"{media.id}_{start}_{start + duration}.mp3"
    if out.exists():
        return out

    ss = f"{start / 1000:.3f}"
    t = f"{duration / 1000:.3f}"
    cmd = [
        ffmpeg,
        "-y",
        "-ss",
        ss,
        "-t",
        t,
        "-i",
        str(src),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "22050",
        "-b:a",
        "64k",
        str(out),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=30)
        if proc.returncode == 0 and out.exists():
            return out
    except (OSError, subprocess.TimeoutExpired):
        return None
    return None


def cards_to_csv(cards: list[Card]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "card_type",
            "headword",
            "meaning_zh",
            "example_en",
            "example_zh",
            "pos",
            "state",
            "due_at",
            "media_id",
            "t_ms",
            "tags",
        ]
    )
    for c in cards:
        writer.writerow(
            [
                getattr(c, "card_type", "word") or "word",
                c.headword,
                c.meaning_zh,
                c.example_en,
                c.example_zh,
                c.pos,
                c.state,
                c.due_at.isoformat() if c.due_at else "",
                c.media_id or "",
                c.t_ms,
                c.tags,
            ]
        )
    return buf.getvalue()


def cards_to_anki_tsv(cards: list[Card]) -> str:
    """Anki import: Basic fields Front/Back + tags. Tabs, no header (Anki style with header optional)."""
    lines = ["#separator:tab", "#html:false", "#tags column:4"]
    lines.append("Front\tBack\tSource\tTags")
    for c in cards:
        front = c.headword
        back_parts = [c.meaning_zh or ""]
        if c.example_en:
            back_parts.append(c.example_en)
        if c.example_zh:
            back_parts.append(c.example_zh)
        back = " | ".join(p for p in back_parts if p)
        source = ""
        if c.media_id is not None:
            source = f"media:{c.media_id}@{c.t_ms}"
        tags = " ".join(t for t in (c.tags.split(",") if c.tags else []) if t) or "leran"
        # Anki TSV: escape newlines
        front = front.replace("\t", " ").replace("\n", " ")
        back = back.replace("\t", " ").replace("\n", " ")
        lines.append(f"{front}\t{back}\t{source}\t{tags}")
    return "\n".join(lines) + "\n"


def build_anki_zip(cards: list[Card], clip_paths: dict[int, Path]) -> bytes:
    """Zip with TSV + audio clips named card_{id}.mp3 for Anki media import."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("leran_cards.tsv", cards_to_anki_tsv(cards))
        for card_id, path in clip_paths.items():
            if path.exists():
                zf.write(path, arcname=f"card_{card_id}.mp3")
    return buf.getvalue()
