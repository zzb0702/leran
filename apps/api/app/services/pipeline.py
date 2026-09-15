from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import settings
from ..models import GlossaryTerm, Media, Segment, User
from .media_tools import (
    AudioSlice,
    extract_asr_audio,
    ffmpeg_bin,
    probe_duration_ms,
    split_audio_chunks,
)
from .providers import resolve_asr, resolve_translate
from .providers.base import AsrSegment, WordSpan

# Serialize heavy pipelines so we don't stampede the LLM provider.
_PIPELINE_LOCK = threading.Lock()


def _set_progress(db: Session, media: Media, status: str, progress: str) -> None:
    media.status = status
    media.progress = progress[:255]
    db.commit()


def _merge_chunk_segments(
    chunk_segs: list[AsrSegment],
    offset_ms: int,
    slice_end_ms: int,
    next_start_ms: int | None,
    *,
    overlap_ms: int,
) -> list[AsrSegment]:
    """Shift chunk-local times to absolute; drop overlap duplicates near the seam."""
    out: list[AsrSegment] = []
    for s in chunk_segs:
        start = s.start_ms + offset_ms
        end = s.end_ms + offset_ms
        # Ignore ASR that fired only in the overlap tail and belongs to the next slice's body
        # when it starts after slice_end and we have a next slice starting there.
        if next_start_ms is not None and start >= slice_end_ms:
            continue
        # Soft-clip end into this slice span (keep a little past end for last word).
        if end > slice_end_ms + overlap_ms:
            end = slice_end_ms + overlap_ms
        if end <= start:
            end = start + 50
        words = [
            type(w)(text=w.text, start_ms=w.start_ms + offset_ms, end_ms=w.end_ms + offset_ms)
            for w in s.words
        ]
        out.append(AsrSegment(start_ms=start, end_ms=end, text=s.text, words=words))
    return out


def _translate_windowed(
    translator,
    texts: list[str],
    glossary: dict[str, str] | None,
    on_batch=None,
) -> list[str]:
    """Translate in batches; call on_batch(start_idx, part_list) after each success."""
    if not texts:
        return []
    batch_n = max(1, settings.translate_batch_size)
    ctx_n = max(0, settings.translate_context_lines)
    delay = max(0.0, settings.translate_delay_s)
    max_retries = max(1, settings.translate_max_retries)
    result: list[str] = []
    total_batches = (len(texts) + batch_n - 1) // batch_n
    for bi, start in enumerate(range(0, len(texts), batch_n)):
        window = texts[start : start + batch_n]
        before = texts[max(0, start - ctx_n) : start]
        after = texts[start + batch_n : start + batch_n + ctx_n]
        part: list[str] | None = None
        last_err: Exception | None = None
        for attempt in range(max_retries):
            try:
                part = translator.translate_batch(
                    window,
                    context_before=before,
                    context_after=after,
                    glossary=glossary,
                )
                break
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                if on_batch:
                    on_batch(
                        None,
                        None,
                        note=f"重试 {attempt + 1}/{max_retries} 批 {bi + 1}/{total_batches}: {str(exc)[:60]}",
                    )
                time.sleep(min(20.0, delay * (2**attempt) + 1.0))
        if part is None:
            raise RuntimeError(f"翻译批次失败 @ 句 {start}: {last_err}")
        if len(part) < len(window):
            part = part + [""] * (len(window) - len(part))
        part = part[: len(window)]
        result.extend(part)
        if on_batch:
            on_batch(start, part, note=f"翻译 {bi + 1}/{total_batches} 批")
        if start + batch_n < len(texts) and delay > 0:
            time.sleep(delay)
    return result


def process_media(db: Session, media_id: int) -> None:
    if not _PIPELINE_LOCK.acquire(timeout=5):
        media = db.get(Media, media_id)
        if media:
            media.status = "queued"
            media.progress = "等待其它任务释放（并发=1）"
            db.commit()
        # block until free
        _PIPELINE_LOCK.acquire()
    try:
        _process_media_locked(db, media_id)
    finally:
        _PIPELINE_LOCK.release()


def _process_media_locked(db: Session, media_id: int) -> None:
    media = db.get(Media, media_id)
    if not media:
        return
    user = db.get(User, media.user_id)
    if not user:
        return

    slices_dir: Path | None = None
    try:
        _set_progress(db, media, "extracting_audio", "准备音频")
        src = settings.media_dir / media.storage_key
        if not src.exists():
            raise FileNotFoundError(f"Media file missing: {media.storage_key}")

        probed = probe_duration_ms(src)
        if probed:
            media.duration_ms = probed
            db.commit()

        asr_input: Path = src
        if settings.extract_audio_for_asr and ffmpeg_bin():
            _set_progress(db, media, "extracting_audio", "抽取 16k 单声道")
            extracted = extract_asr_audio(src)
            if extracted and extracted.exists():
                media.audio_storage_key = extracted.relative_to(settings.media_dir).as_posix()
                asr_input = extracted
                db.commit()

        duration_ms = media.duration_ms or (probe_duration_ms(asr_input) or 0)
        chunk_minutes = settings.asr_chunk_minutes
        need_split = duration_ms > chunk_minutes * 60 * 1000 or (
            ffmpeg_bin() and asr_input.stat().st_size > settings.openai_max_file_mb * 1024 * 1024
        )

        slices: list[AudioSlice]
        if need_split and ffmpeg_bin():
            slices_dir = asr_input.parent / f"{asr_input.stem}_asr_slices"
            _set_progress(
                db,
                media,
                "extracting_audio",
                f"切片 ASR（每段约 {chunk_minutes:.0f} 分钟）",
            )
            slices = split_audio_chunks(
                asr_input,
                duration_ms,
                chunk_minutes=chunk_minutes,
                work_dir=slices_dir,
            )
        else:
            slices = [AudioSlice(path=asr_input, start_ms=0, end_ms=duration_ms)]

        asr = resolve_asr(db, user, media.asr_provider)
        translator = resolve_translate(db, user, media.translate_provider)

        # Cache ASR on disk so reprocess after translate failure does not re-run whisper.
        asr_cache = (
            settings.media_dir / media.storage_key
        ).with_suffix(".asr.json")
        raw_segments: list[AsrSegment] = []
        if asr_cache.exists() and asr_cache.stat().st_size > 0:
            try:
                payload = json.loads(asr_cache.read_text(encoding="utf-8"))
                for item in payload:
                    words = [
                        WordSpan(text=w["text"], start_ms=w["start_ms"], end_ms=w["end_ms"])
                        for w in item.get("words") or []
                    ]
                    raw_segments.append(
                        AsrSegment(
                            start_ms=item["start_ms"],
                            end_ms=item["end_ms"],
                            text=item["text"],
                            words=words,
                        )
                    )
                media.progress = f"使用缓存识别结果（{len(raw_segments)} 句）"
                db.commit()
            except Exception:  # noqa: BLE001
                raw_segments = []

        if not raw_segments:
            n = len(slices)
            for i, sl in enumerate(slices):
                _set_progress(db, media, "transcribing", f"识别 {i + 1}/{n} 段")
                chunk = asr.transcribe(str(sl.path), language="en")
                next_start = slices[i + 1].start_ms if i + 1 < n else None
                raw_segments.extend(
                    _merge_chunk_segments(
                        chunk,
                        sl.start_ms,
                        sl.end_ms,
                        next_start,
                        overlap_ms=settings.asr_chunk_overlap_ms,
                    )
                )
            # write cache
            try:
                asr_cache.parent.mkdir(parents=True, exist_ok=True)
                asr_cache.write_text(
                    json.dumps(
                        [
                            {
                                "start_ms": s.start_ms,
                                "end_ms": s.end_ms,
                                "text": s.text,
                                "words": [
                                    {
                                        "text": w.text,
                                        "start_ms": w.start_ms,
                                        "end_ms": w.end_ms,
                                    }
                                    for w in s.words
                                ],
                            }
                            for s in raw_segments
                        ],
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
            except OSError:
                pass

        # Sort + drop empties + light dedupe of identical adjacent seams
        raw_segments = [s for s in raw_segments if s.text.strip()]
        raw_segments.sort(key=lambda s: (s.start_ms, s.end_ms))
        deduped: list[AsrSegment] = []
        for s in raw_segments:
            if deduped and s.text.strip().lower() == deduped[-1].text.strip().lower():
                if abs(s.start_ms - deduped[-1].start_ms) < 1200:
                    continue
            deduped.append(s)
        raw_segments = deduped

        if not raw_segments:
            raise RuntimeError("ASR produced no segments (check audio / provider)")

        # Persist English first so the UI is never empty while translating.
        db.query(Segment).filter(Segment.media_id == media.id).delete()
        db.commit()
        duration = media.duration_ms
        seg_rows: list[Segment] = []
        for i, rs in enumerate(raw_segments):
            seg = Segment(
                media_id=media.id,
                idx=i,
                start_ms=rs.start_ms,
                end_ms=rs.end_ms,
                raw_en=rs.text,
                raw_zh="",
                words_json=json.dumps(
                    [
                        {"text": w.text, "start_ms": w.start_ms, "end_ms": w.end_ms}
                        for w in rs.words
                    ]
                ),
            )
            db.add(seg)
            seg_rows.append(seg)
            duration = max(duration, rs.end_ms)
            if i % 80 == 79:
                media.progress = f"写入英文 {i + 1}/{len(raw_segments)}"
                db.commit()
        if duration:
            media.duration_ms = duration
        db.commit()
        db.refresh(media)

        texts = [s.text for s in raw_segments]
        glossary_rows = db.query(GlossaryTerm).filter(GlossaryTerm.user_id == user.id).all()
        glossary = {r.term: (r.keep_as or r.term) for r in glossary_rows} or None

        translate_warn = ""
        try:
            _set_progress(db, media, "translating", f"翻译 0/{len(texts)} 句")

            def _on_batch(start, part, note=""):
                if start is not None and part is not None:
                    for j, zh in enumerate(part):
                        idx = start + j
                        if 0 <= idx < len(seg_rows):
                            seg_rows[idx].raw_zh = zh
                    db.commit()
                    done = min(len(texts), start + len(part))
                    media.progress = f"翻译 {done}/{len(texts)} 句"
                    db.commit()
                elif note:
                    media.progress = note[:255]
                    db.commit()

            translations = _translate_windowed(
                translator, texts, glossary, on_batch=_on_batch
            )
            for i, row in enumerate(seg_rows):
                if translations[i]:
                    row.raw_zh = translations[i]
            db.commit()
        except Exception as texc:  # noqa: BLE001
            translate_warn = f"翻译中断（英文已保留）：{texc}"
            media.progress = translate_warn[:255]
            db.commit()

        media.status = "ready"
        media.progress = (
            f"完成 · {len(raw_segments)} 句"
            + (" · 中文待重试" if translate_warn else "")
        )
        media.error = translate_warn
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        media = db.get(Media, media_id)
        if media:
            media.status = "failed"
            media.error = str(exc)
            media.progress = ""
            db.commit()
    finally:
        # Cleanup temporary ASR slices to save disk on 45min+ episodes
        if slices_dir and slices_dir.exists():
            try:
                for p in slices_dir.glob("slice_*"):
                    p.unlink(missing_ok=True)
                slices_dir.rmdir()
            except OSError:
                pass


def estimate_duration_ms(path: Path) -> int:
    probed = probe_duration_ms(path)
    if probed:
        return probed
    try:
        size = path.stat().st_size
        return max(0, min(size // 17_000, 3 * 60 * 60 * 1000))
    except OSError:
        return 0
