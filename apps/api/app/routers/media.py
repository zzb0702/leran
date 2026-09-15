from __future__ import annotations

import json
import re
import threading
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import settings
from ..db import get_db
from ..models import Card, Media, Segment, User
from ..schemas import (
    MediaOut,
    SegmentOut,
    SegmentUpdate,
    UploadCompleteIn,
    UploadInitOut,
    WordSpan,
)
from ..services.media_tools import safe_filename
from ..services.pipeline import estimate_duration_ms, process_media
from ..services.subtitle import segments_to_srt, segments_to_vtt

router = APIRouter(prefix="/api/media", tags=["media"])

# In-memory upload sessions (single-node MVP). upload_id -> meta
_UPLOADS: dict[str, dict] = {}


def _media_out(db: Session, media: Media) -> MediaOut:
    seg_count = db.query(Segment).filter(Segment.media_id == media.id).count()
    card_count = db.query(Card).filter(Card.media_id == media.id).count()
    out = MediaOut.model_validate(media)
    out.segment_count = seg_count
    out.card_count = card_count
    return out


def _segment_out(seg: Segment) -> SegmentOut:
    try:
        words = [WordSpan(**w) for w in json.loads(seg.words_json or "[]")]
    except Exception:  # noqa: BLE001
        words = []
    return SegmentOut(
        id=seg.id,
        media_id=seg.media_id,
        idx=seg.idx,
        start_ms=seg.start_ms,
        end_ms=seg.end_ms,
        text_en=seg.text_en,
        text_zh=seg.text_zh,
        raw_en=seg.raw_en,
        raw_zh=seg.raw_zh,
        words=words,
    )


def _spawn_process(media_id: int) -> None:
    def _run() -> None:
        from ..db import SessionLocal

        session = SessionLocal()
        try:
            process_media(session, media_id)
        finally:
            session.close()

    threading.Thread(target=_run, daemon=True).start()


def _user_default_providers(db: Session, user: User) -> tuple[str, str]:
    """Use saved Settings providers; fall back to env/mock."""
    from ..models import ProviderConfig

    asr = settings.asr_provider or "mock"
    tr = settings.translate_provider or "mock"
    rows = (
        db.query(ProviderConfig)
        .filter(ProviderConfig.user_id == user.id, ProviderConfig.kind.in_(["asr", "translate"]))
        .all()
    )
    for r in rows:
        if r.kind == "asr" and r.provider_id:
            asr = r.provider_id
        if r.kind == "translate" and r.provider_id:
            tr = r.provider_id
    return asr, tr


def _finalize_media(
    db: Session,
    user: User,
    dest: Path,
    *,
    title: str,
    filename: str,
    asr_provider: str,
    translate_provider: str,
) -> MediaOut:
    default_asr, default_tr = _user_default_providers(db, user)
    asr_provider = (asr_provider or "").strip() or default_asr
    translate_provider = (translate_provider or "").strip() or default_tr
    suffix = dest.suffix or ".mp4"
    stem = dest.stem
    storage_rel = dest.relative_to(settings.media_dir).as_posix()
    media = Media(
        user_id=user.id,
        title=(title or stem).strip()[:200],
        storage_key=storage_rel,
        duration_ms=estimate_duration_ms(dest),
        file_size=dest.stat().st_size if dest.exists() else 0,
        status="queued",
        asr_provider=asr_provider,
        translate_provider=translate_provider,
    )
    db.add(media)
    db.commit()
    db.refresh(media)
    _spawn_process(media.id)
    return _media_out(db, media)


@router.get("", response_model=list[MediaOut])
def list_media(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[MediaOut]:
    rows = (
        db.query(Media)
        .filter(Media.user_id == user.id)
        .order_by(Media.updated_at.desc())
        .all()
    )
    return [_media_out(db, m) for m in rows]


@router.get("/limits")
def upload_limits() -> dict:
    return {
        "max_upload_mb": settings.max_upload_mb,
        "chunk_size_mb": settings.chunk_size_mb,
        "max_upload_bytes": settings.max_upload_mb * 1024 * 1024,
        "chunk_size_bytes": settings.chunk_size_mb * 1024 * 1024,
    }


class ChunkMeta(BaseModel):
    upload_id: str
    index: int
    total_chunks: int
    total_size: int = 0


@router.post("/upload/init", response_model=UploadInitOut)
async def upload_init(
    body: ChunkMeta,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UploadInitOut:
    if body.total_size and body.total_size > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {settings.max_upload_mb}MB)",
        )
    upload_id = uuid.uuid4().hex
    tmp_dir = settings.upload_tmp_dir / str(user.id) / upload_id
    tmp_dir.mkdir(parents=True, exist_ok=True)
    _UPLOADS[upload_id] = {
        "user_id": user.id,
        "tmp_dir": str(tmp_dir),
        "total_chunks": body.total_chunks,
        "received": set(),
        "total_size": body.total_size,
        "filename": "",
    }
    return UploadInitOut(
        upload_id=upload_id,
        storage_key=f"{user.id}/{upload_id}",
        chunk_size_bytes=settings.chunk_size_mb * 1024 * 1024,
        max_upload_bytes=settings.max_upload_mb * 1024 * 1024,
    )


@router.post("/upload/chunk")
async def upload_chunk(
    upload_id: str = Form(...),
    index: int = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
) -> dict:
    sess = _UPLOADS.get(upload_id)
    if not sess or sess["user_id"] != user.id:
        raise HTTPException(status_code=404, detail="Upload session not found")
    tmp_dir = Path(sess["tmp_dir"])
    part = tmp_dir / f"part_{index:06d}"
    size = 0
    max_bytes = settings.max_upload_mb * 1024 * 1024
    async with aiofiles.open(part, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                raise HTTPException(status_code=413, detail="Chunk too large")
            await out.write(chunk)
    sess["received"].add(index)
    if file.filename and not sess.get("filename"):
        sess["filename"] = file.filename
    return {
        "ok": True,
        "received": len(sess["received"]),
        "total_chunks": sess["total_chunks"],
    }


@router.post("/upload/complete", response_model=MediaOut)
async def upload_complete(
    body: UploadCompleteIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MediaOut:
    sess = _UPLOADS.get(body.upload_id)
    if not sess or sess["user_id"] != user.id:
        raise HTTPException(status_code=404, detail="Upload session not found")
    expected = set(range(sess["total_chunks"]))
    if sess["received"] != expected:
        missing = sorted(expected - sess["received"])
        raise HTTPException(status_code=400, detail=f"Missing chunks: {missing[:10]}")

    filename = safe_filename(body.filename or sess.get("filename") or "upload.bin")
    suffix = Path(filename).suffix or ".bin"
    storage_key = f"{user.id}/{uuid.uuid4().hex[:10]}_{Path(filename).stem}{suffix}"
    dest = settings.media_dir / storage_key
    dest.parent.mkdir(parents=True, exist_ok=True)

    tmp_dir = Path(sess["tmp_dir"])
    written = 0
    with open(dest, "wb") as out:
        for i in range(sess["total_chunks"]):
            part = tmp_dir / f"part_{i:06d}"
            with open(part, "rb") as src:
                while True:
                    buf = src.read(1024 * 1024)
                    if not buf:
                        break
                    out.write(buf)
                    written += len(buf)

    # Cleanup tmp
    for p in tmp_dir.glob("part_*"):
        p.unlink(missing_ok=True)
    tmp_dir.rmdir()
    _UPLOADS.pop(body.upload_id, None)

    if body.total_size and written > settings.max_upload_mb * 1024 * 1024:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=413, detail="File too large")

    return _finalize_media(
        db,
        user,
        dest,
        title=body.title,
        filename=filename,
        asr_provider=body.asr_provider,
        translate_provider=body.translate_provider,
    )


@router.post("/upload", response_model=MediaOut)
async def upload_media(
    file: UploadFile = File(...),
    title: str = Form(""),
    asr_provider: str = Form(""),
    translate_provider: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MediaOut:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing file")

    filename = safe_filename(file.filename)
    suffix = Path(filename).suffix or ".bin"
    storage_key = f"{user.id}/{uuid.uuid4().hex[:10]}_{Path(filename).stem}{suffix}"
    dest = settings.media_dir / storage_key
    dest.parent.mkdir(parents=True, exist_ok=True)

    size = 0
    max_bytes = settings.max_upload_mb * 1024 * 1024
    async with aiofiles.open(dest, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                await out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large (max {settings.max_upload_mb}MB)",
                )
            await out.write(chunk)

    return _finalize_media(
        db,
        user,
        dest,
        title=title,
        filename=filename,
        asr_provider=asr_provider,
        translate_provider=translate_provider,
    )


@router.get("/{media_id}", response_model=MediaOut)
def get_media(
    media_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MediaOut:
    media = db.get(Media, media_id)
    if not media or media.user_id != user.id:
        raise HTTPException(status_code=404, detail="Media not found")
    return _media_out(db, media)


class ReprocessIn(BaseModel):
    asr_provider: str = ""
    translate_provider: str = ""


@router.post("/{media_id}/reprocess", response_model=MediaOut)
def reprocess_media(
    media_id: int,
    body: ReprocessIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MediaOut:
    media = db.get(Media, media_id)
    if not media or media.user_id != user.id:
        raise HTTPException(status_code=404, detail="Media not found")
    default_asr, default_tr = _user_default_providers(db, user)
    # Prefer explicit body, then user's Settings, then keep existing non-mock
    if body and body.asr_provider:
        media.asr_provider = body.asr_provider
    else:
        media.asr_provider = default_asr
    if body and body.translate_provider:
        media.translate_provider = body.translate_provider
    else:
        media.translate_provider = default_tr
    media.status = "queued"
    media.error = ""
    media.progress = "排队中"
    db.commit()
    _spawn_process(media.id)
    db.refresh(media)
    return _media_out(db, media)


@router.delete("/{media_id}")
def delete_media(
    media_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    media = db.get(Media, media_id)
    if not media or media.user_id != user.id:
        raise HTTPException(status_code=404, detail="Media not found")
    (settings.media_dir / media.storage_key).unlink(missing_ok=True)
    if media.audio_storage_key:
        (settings.media_dir / media.audio_storage_key).unlink(missing_ok=True)
    db.delete(media)
    db.commit()
    return {"ok": True}


@router.get("/{media_id}/segments", response_model=list[SegmentOut])
def list_segments(
    media_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[SegmentOut]:
    media = db.get(Media, media_id)
    if not media or media.user_id != user.id:
        raise HTTPException(status_code=404, detail="Media not found")
    segs = (
        db.query(Segment)
        .filter(Segment.media_id == media_id)
        .order_by(Segment.idx)
        .all()
    )
    return [_segment_out(s) for s in segs]


@router.patch("/segments/{segment_id}", response_model=SegmentOut)
def update_segment(
    segment_id: int,
    body: SegmentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SegmentOut:
    seg = db.get(Segment, segment_id)
    if not seg:
        raise HTTPException(status_code=404, detail="Segment not found")
    media = db.get(Media, seg.media_id)
    if not media or media.user_id != user.id:
        raise HTTPException(status_code=404, detail="Segment not found")

    if body.edited_en is not None:
        seg.edited_en = body.edited_en
    if body.edited_zh is not None:
        seg.edited_zh = body.edited_zh
    if body.start_ms is not None:
        seg.start_ms = body.start_ms
    if body.end_ms is not None:
        seg.end_ms = body.end_ms
    db.commit()
    db.refresh(seg)
    return _segment_out(seg)


@router.get("/{media_id}/export")
def export_media(
    media_id: int,
    format: str = "srt",
    lang: str = "bilingual",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    media = db.get(Media, media_id)
    if not media or media.user_id != user.id:
        raise HTTPException(status_code=404, detail="Media not found")
    segs = (
        db.query(Segment)
        .filter(Segment.media_id == media_id)
        .order_by(Segment.idx)
        .all()
    )
    if format == "vtt":
        content = segments_to_vtt(segs, lang=lang)
        media_type = "text/vtt"
        ext = "vtt"
    else:
        content = segments_to_srt(segs, lang=lang)
        media_type = "text/plain"
        ext = "srt"
    filename = f"{media.title}.{lang}.{ext}"
    return PlainTextResponse(
        content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _user_from_token(db: Session, token: str) -> User | None:
    from jose import JWTError, jwt

    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return db.get(User, int(payload.get("sub")))
    except (JWTError, TypeError, ValueError):
        return None


@router.get("/{media_id}/file")
def stream_media_file(
    media_id: int,
    request: Request,
    token: str = "",
    range_header: str | None = Header(default=None, alias="Range"),
    db: Session = Depends(get_db),
):
    """Range-enabled file stream so large videos can seek in <video>."""
    from fastapi.responses import FileResponse

    user = _user_from_token(db, token)
    if not user:
        auth = request.headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            user = _user_from_token(db, auth[7:].strip())
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    media = db.get(Media, media_id)
    if not media or media.user_id != user.id:
        raise HTTPException(status_code=404, detail="Media not found")
    path = settings.media_dir / media.storage_key
    if not path.exists():
        raise HTTPException(status_code=404, detail="File missing")

    file_size = path.stat().st_size
    content_type = "application/octet-stream"
    suffix = path.suffix.lower()
    if suffix in {".mp4", ".m4v"}:
        content_type = "video/mp4"
    elif suffix == ".webm":
        content_type = "video/webm"
    elif suffix in {".mkv"}:
        content_type = "video/x-matroska"
    elif suffix in {".mov"}:
        content_type = "video/quicktime"
    elif suffix == ".mp3":
        content_type = "audio/mpeg"
    elif suffix in {".wav"}:
        content_type = "audio/wav"
    elif suffix in {".m4a", ".aac"}:
        content_type = "audio/mp4"

    if not range_header:
        return FileResponse(path, media_type=content_type)

    # Parse "bytes=start-end"
    m = re.match(r"bytes=(\d*)-(\d*)", range_header)
    if not m:
        return FileResponse(path, media_type=content_type)
    start_s, end_s = m.group(1), m.group(2)
    start = int(start_s) if start_s else 0
    end = int(end_s) if end_s else file_size - 1
    end = min(end, file_size - 1)
    if start > end or start >= file_size:
        raise HTTPException(status_code=416, detail="Invalid Range")

    chunk_size = 1024 * 1024

    def iter_file():
        with open(path, "rb") as f:
            f.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                data = f.read(min(chunk_size, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(end - start + 1),
    }
    return StreamingResponse(iter_file(), status_code=206, media_type=content_type, headers=headers)


@router.get("/{media_id}/thumb")
def media_thumb(
    media_id: int,
    request: Request,
    token: str = "",
    db: Session = Depends(get_db),
):
    """First-frame JPEG thumbnail (ffmpeg, cached under data/thumbs)."""
    from fastapi.responses import FileResponse

    from ..services.export_cards import ffmpeg_bin

    user = _user_from_token(db, token)
    if not user:
        auth = request.headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            user = _user_from_token(db, auth[7:].strip())
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    media = db.get(Media, media_id)
    if not media or media.user_id != user.id:
        raise HTTPException(status_code=404, detail="Media not found")

    thumb_dir = Path(settings.media_dir).parent / "thumbs"
    thumb = thumb_dir / f"{media.id}.jpg"
    if not thumb.exists():
        ff = ffmpeg_bin()
        src = settings.media_dir / media.storage_key
        if not ff or not src.exists():
            raise HTTPException(status_code=404, detail="Thumbnail unavailable")
        thumb_dir.mkdir(parents=True, exist_ok=True)
        import subprocess

        try:
            subprocess.run(
                [
                    ff, "-y", "-ss", "3", "-i", str(src),
                    "-frames:v", "1", "-vf", "scale=480:-2", str(thumb),
                ],
                check=True,
                capture_output=True,
                timeout=60,
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail="Thumbnail extraction failed") from exc
    return FileResponse(thumb, media_type="image/jpeg")
