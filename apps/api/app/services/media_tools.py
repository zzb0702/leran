from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..config import settings

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v", ".flv", ".wmv", ".ts"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma"}


def ffmpeg_bin() -> str | None:
    if settings.ffmpeg_path:
        p = Path(settings.ffmpeg_path)
        if p.exists():
            return str(p)
    return shutil.which("ffmpeg")


def ffprobe_bin() -> str | None:
    if settings.ffprobe_path:
        p = Path(settings.ffprobe_path)
        if p.exists():
            return str(p)
    which = shutil.which("ffprobe")
    if which:
        return which
    # Derive from ffmpeg path (same folder in full builds).
    ff = ffmpeg_bin()
    if ff:
        cand = Path(ff).with_name("ffprobe.exe")
        if cand.exists():
            return str(cand)
        cand2 = Path(ff).with_name("ffprobe")
        if cand2.exists():
            return str(cand2)
    return None


def is_video(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTS


def is_audio(path: Path) -> bool:
    return path.suffix.lower() in AUDIO_EXTS


def probe_duration_ms(path: Path) -> int | None:
    """Return duration in ms via ffprobe, or None if unavailable."""
    probe = ffprobe_bin()
    if not probe or not path.exists():
        return None
    cmd = [
        probe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            return None
        raw = (proc.stdout or "").strip().splitlines()
        if not raw:
            return None
        return int(float(raw[0]) * 1000)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def extract_asr_audio(src: Path, dest: Path | None = None) -> Path | None:
    """
    Extract 16kHz mono wav/mp3 for speech recognition.
    Much smaller/faster to feed ASR than full video.
    Returns dest path or None if ffmpeg missing / already audio-only without need.
    """
    ffmpeg = ffmpeg_bin()
    if not ffmpeg:
        return None

    if dest is None:
        dest = src.with_suffix(".asr.wav")

    if dest.exists() and dest.stat().st_size > 0:
        return dest

    # Already compact audio: still normalize to 16k mono for consistent ASR.
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(src),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(dest),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=max(60, settings.audio_extract_timeout_s))
        if proc.returncode == 0 and dest.exists() and dest.stat().st_size > 0:
            return dest
        # Fallback: mp3 if wav encode failed for some builds
        dest_mp3 = dest.with_suffix(".asr.mp3")
        cmd_mp3 = [
            ffmpeg,
            "-y",
            "-i",
            str(src),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-b:a",
            "48k",
            str(dest_mp3),
        ]
        proc2 = subprocess.run(cmd_mp3, capture_output=True, timeout=max(60, settings.audio_extract_timeout_s))
        if proc2.returncode == 0 and dest_mp3.exists():
            return dest_mp3
    except (OSError, subprocess.TimeoutExpired):
        return None
    return None


def safe_filename(name: str) -> str:
    stem = Path(name).stem
    suffix = Path(name).suffix
    stem = re.sub(r"[^\w.-]+", "_", stem)[:80] or "media"
    return f"{stem}{suffix}"


def file_size_mb(path: Path) -> float:
    try:
        return path.stat().st_size / (1024 * 1024)
    except OSError:
        return 0.0


@dataclass
class AudioSlice:
    path: Path
    start_ms: int
    end_ms: int


def split_audio_chunks(
    src: Path,
    duration_ms: int,
    *,
    chunk_minutes: float | None = None,
    overlap_ms: int | None = None,
    work_dir: Path | None = None,
) -> list[AudioSlice]:
    """
    Slice a long audio file for ASR (e.g. 45min episode → 10min pieces).
    Overlap helps avoid cutting words at boundaries; offsets are applied when merging.
    """
    ffmpeg = ffmpeg_bin()
    chunk_ms = int((chunk_minutes or settings.asr_chunk_minutes) * 60 * 1000)
    overlap = overlap_ms if overlap_ms is not None else settings.asr_chunk_overlap_ms

    if duration_ms <= 0:
        probed = probe_duration_ms(src)
        duration_ms = probed or 0
    if duration_ms <= chunk_ms:
        return [AudioSlice(path=src, start_ms=0, end_ms=duration_ms or 0)]

    if not ffmpeg:
        # No ffmpeg: still one piece; provider may fail on huge files.
        return [AudioSlice(path=src, start_ms=0, end_ms=duration_ms)]

    out_dir = work_dir or (src.parent / f"{src.stem}_asr_slices")
    out_dir.mkdir(parents=True, exist_ok=True)

    slices: list[AudioSlice] = []
    t = 0
    idx = 0
    while t < duration_ms:
        piece = min(chunk_ms, duration_ms - t)
        # Include overlap into next start for boundary words, but keep this piece's span.
        encode_len = piece + min(overlap, duration_ms - t - piece) if t + piece < duration_ms else piece
        out = out_dir / f"slice_{idx:03d}_{t}_{t + piece}.wav"
        cmd = [
            ffmpeg,
            "-y",
            "-ss",
            f"{t / 1000:.3f}",
            "-t",
            f"{encode_len / 1000:.3f}",
            "-i",
            str(src),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(out),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=300)
            if proc.returncode != 0 or not out.exists():
                raise RuntimeError(f"ffmpeg slice failed at {t}ms")
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"ffmpeg slice error at {t}ms: {exc}") from exc
        slices.append(AudioSlice(path=out, start_ms=t, end_ms=t + piece))
        idx += 1
        t += piece
    return slices

