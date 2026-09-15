from __future__ import annotations

from sqlalchemy.orm import Session

from ...config import settings
from ...models import ProviderConfig, User
from .base import AsrProvider, EnrichProvider, TranslateProvider
from .local_whisper import LocalWhisperProvider
from .mock import MockAsrProvider, MockEnrichProvider, MockTranslateProvider
from .openai_compat import OpenAiAsrProvider, OpenAiEnrichProvider, OpenAiTranslateProvider


def _user_provider(db: Session, user_id: int, kind: str) -> ProviderConfig | None:
    return (
        db.query(ProviderConfig)
        .filter(ProviderConfig.user_id == user_id, ProviderConfig.kind == kind)
        .first()
    )


def resolve_asr(db: Session, user: User, override: str = "") -> AsrProvider:
    cfg = _user_provider(db, user.id, "asr")
    pid = override or (cfg.provider_id if cfg else settings.asr_provider)
    if pid == "openai":
        return OpenAiAsrProvider(
            api_key=cfg.api_key if cfg else None,
            base_url=cfg.base_url if cfg else None,
            model=cfg.model if cfg else None,
        )
    if pid in {"local-whisper", "faster-whisper", "whisper"}:
        model = (cfg.model if cfg and cfg.model else None) or settings.local_whisper_model
        return LocalWhisperProvider(model_size=model)
    return MockAsrProvider()


def resolve_translate(db: Session, user: User, override: str = "") -> TranslateProvider:
    cfg = _user_provider(db, user.id, "translate")
    pid = override or (cfg.provider_id if cfg else settings.translate_provider)
    if pid == "openai":
        return OpenAiTranslateProvider(
            api_key=cfg.api_key if cfg else None,
            base_url=cfg.base_url if cfg else None,
            model=cfg.model if cfg else None,
        )
    return MockTranslateProvider()


def resolve_enrich(db: Session, user: User, override: str = "") -> EnrichProvider:
    cfg = _user_provider(db, user.id, "enrich")
    pid = override or (cfg.provider_id if cfg else settings.enrich_provider)
    if pid == "openai":
        return OpenAiEnrichProvider(
            api_key=cfg.api_key if cfg else None,
            base_url=cfg.base_url if cfg else None,
            model=cfg.model if cfg else None,
        )
    return MockEnrichProvider()
