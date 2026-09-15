from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import get_db
from ..models import GlossaryTerm, ProviderConfig, User
from ..schemas import GlossaryIn, GlossaryOut, ProviderConfigIn, ProviderConfigOut

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/providers", response_model=list[ProviderConfigOut])
def list_providers(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ProviderConfigOut]:
    rows = db.query(ProviderConfig).filter(ProviderConfig.user_id == user.id).all()
    out: list[ProviderConfigOut] = []
    seen = {r.kind for r in rows}
    for r in rows:
        out.append(
            ProviderConfigOut(
                kind=r.kind,
                provider_id=r.provider_id,
                base_url=r.base_url,
                model=r.model,
                has_api_key=bool(r.api_key),
            )
        )
    for kind in ("asr", "translate", "enrich", "dict"):
        if kind not in seen:
            out.append(
                ProviderConfigOut(
                    kind=kind,
                    provider_id="baidu" if kind == "dict" else "mock",
                    base_url="",
                    model="",
                    has_api_key=False,
                )
            )
    return out


@router.put("/providers", response_model=ProviderConfigOut)
def upsert_provider(
    body: ProviderConfigIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProviderConfigOut:
    if body.kind not in {"asr", "translate", "enrich", "dict"}:
        raise HTTPException(status_code=400, detail="Invalid kind")
    row = (
        db.query(ProviderConfig)
        .filter(ProviderConfig.user_id == user.id, ProviderConfig.kind == body.kind)
        .first()
    )
    if not row:
        row = ProviderConfig(user_id=user.id, kind=body.kind)
        db.add(row)
    row.provider_id = body.provider_id
    row.base_url = body.base_url
    row.model = body.model
    if body.api_key:
        row.api_key = body.api_key
    db.commit()
    db.refresh(row)
    return ProviderConfigOut(
        kind=row.kind,
        provider_id=row.provider_id,
        base_url=row.base_url,
        model=row.model,
        has_api_key=bool(row.api_key),
    )


class ProviderTestIn(BaseModel):
    kind: str
    # Optional unsaved form values (so you can test before 保存)
    provider_id: str = ""
    api_key: str = ""
    base_url: str = ""
    model: str = ""


class ProviderTestOut(BaseModel):
    ok: bool
    kind: str
    provider_id: str
    message: str
    sample: str = ""


def _make_test_wav(path: Path, duration_s: float = 1.2, freq: float = 440.0) -> Path:
    """Tiny mono 16k wav so ASR smoke test does not depend on user media."""
    import math
    import struct
    import wave

    rate = 16000
    n = int(rate * duration_s)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = bytearray()
        for i in range(n):
            # mild envelope so it is not a pure DC click
            env = min(1.0, i / 800.0, (n - i) / 800.0)
            val = int(12000 * env * math.sin(2 * math.pi * freq * i / rate))
            frames += struct.pack("<h", val)
        w.writeframes(frames)
    return path


@router.post("/providers/test", response_model=ProviderTestOut)
def test_provider(
    body: ProviderTestIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProviderTestOut:
    """Smoke-test ASR / translate / enrich before using them on a real video."""
    from ..config import settings
    from ..services.providers.mock import MockAsrProvider, MockEnrichProvider, MockTranslateProvider
    from ..services.providers.openai_compat import (
        OpenAiAsrProvider,
        OpenAiEnrichProvider,
        OpenAiTranslateProvider,
    )
    from ..services.providers.local_whisper import LocalWhisperProvider

    if body.kind not in {"asr", "translate", "enrich", "dict"}:
        raise HTTPException(status_code=400, detail="Invalid kind")

    # Prefer form values; fall back to saved config; fall back to defaults.
    saved = (
        db.query(ProviderConfig)
        .filter(ProviderConfig.user_id == user.id, ProviderConfig.kind == body.kind)
        .first()
    )
    pid = body.provider_id or (saved.provider_id if saved else "mock")
    api_key = body.api_key or (saved.api_key if saved else "")
    base_url = body.base_url or (saved.base_url if saved else "")
    model = body.model or (saved.model if saved else "")

    try:
        if body.kind == "translate":
            if pid == "openai":
                provider = OpenAiTranslateProvider(api_key=api_key, base_url=base_url, model=model)
            else:
                provider = MockTranslateProvider()
            out = provider.translate_batch(
                ["Hello, this is a Leran provider test."],
                context_before=[],
                context_after=[],
                glossary=None,
            )
            sample = out[0] if out else ""
            if not sample.strip():
                raise RuntimeError("翻译返回空结果")
            return ProviderTestOut(
                ok=True,
                kind="translate",
                provider_id=pid,
                message=f"翻译可用（{pid}）",
                sample=sample,
            )

        if body.kind == "enrich":
            if pid == "openai":
                provider = OpenAiEnrichProvider(api_key=api_key, base_url=base_url, model=model)
            else:
                provider = MockEnrichProvider()
            draft = provider.define_in_context(
                "throughput",
                "That means throughput goes up when the workload can be split.",
            )
            meaning = (draft or {}).get("meaning_zh") or ""
            if not meaning.strip():
                raise RuntimeError("释义返回空结果")
            return ProviderTestOut(
                ok=True,
                kind="enrich",
                provider_id=pid,
                message=f"释义可用（{pid}）",
                sample=meaning,
            )

        if body.kind == "dict":
            from ..services.dict_api import fetch_baidu

            pid = pid or "baidu"
            if pid != "baidu":
                raise HTTPException(status_code=400, detail="Unknown dict provider")
            if not (model and api_key):
                raise RuntimeError("请填写 APP ID 和密钥（百度翻译开放平台 → 开发者信息）")
            payload = fetch_baidu("apple", model, api_key)
            if not payload:
                raise RuntimeError(
                    "查询失败：检查 APP ID/密钥是否正确、免费额度是否用尽、或网络是否可达"
                )
            return ProviderTestOut(
                ok=True,
                kind="dict",
                provider_id=pid,
                message="百度翻译查词可用",
                sample=f"apple → {payload['meaning_zh']}",
            )

        # ASR
        speech = Path(settings.clip_dir) / "_provider_test" / "test.wav"
        # Prefer a real speech sample if present next to project data/
        candidate = Path(settings.media_dir).parent / "speech-sample.wav"
        if candidate.exists():
            test_audio = candidate
        else:
            test_audio = _make_test_wav(speech)

        if pid in {"local-whisper", "faster-whisper", "whisper"}:
            provider = LocalWhisperProvider(model_size=model or settings.local_whisper_model)
        elif pid == "openai":
            provider = OpenAiAsrProvider(api_key=api_key, base_url=base_url, model=model)
        else:
            provider = MockAsrProvider()

        segs = provider.transcribe(str(test_audio), language="en")
        text = " ".join(s.text.strip() for s in segs if s.text.strip())
        if pid == "mock" and not text:
            text = "(mock)"
        # Mock on a pure sine may return demo lines — that still proves the chain works.
        if not text and pid != "mock":
            # silent tone often yields empty; treat load+call success as OK with note
            return ProviderTestOut(
                ok=True,
                kind="asr",
                provider_id=pid,
                message=f"ASR 调用成功（{pid}），测试音为静音/音调，无识别文本属正常",
                sample="",
            )
        return ProviderTestOut(
            ok=True,
            kind="asr",
            provider_id=pid,
            message=f"ASR 可用（{pid}）",
            sample=text[:200],
        )
    except Exception as exc:  # noqa: BLE001
        return ProviderTestOut(
            ok=False,
            kind=body.kind,
            provider_id=pid,
            message=str(exc)[:500],
            sample="",
        )


@router.get("/glossary", response_model=list[GlossaryOut])
def list_glossary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[GlossaryTerm]:
    return db.query(GlossaryTerm).filter(GlossaryTerm.user_id == user.id).all()


@router.post("/glossary", response_model=GlossaryOut)
def add_glossary(
    body: GlossaryIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> GlossaryTerm:
    row = (
        db.query(GlossaryTerm)
        .filter(GlossaryTerm.user_id == user.id, GlossaryTerm.term == body.term)
        .first()
    )
    if not row:
        row = GlossaryTerm(user_id=user.id, term=body.term)
        db.add(row)
    row.keep_as = body.keep_as
    row.note = body.note
    db.commit()
    db.refresh(row)
    return row


@router.delete("/glossary/{term_id}")
def delete_glossary(
    term_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    row = db.get(GlossaryTerm, term_id)
    if not row or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(row)
    db.commit()
    return {"ok": True}
