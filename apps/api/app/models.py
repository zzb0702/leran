from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    media: Mapped[list[Media]] = relationship(back_populates="user")
    decks: Mapped[list[Deck]] = relationship(back_populates="user")
    providers: Mapped[list[ProviderConfig]] = relationship(back_populates="user")


class ProviderConfig(Base):
    __tablename__ = "provider_configs"
    __table_args__ = (UniqueConstraint("user_id", "kind", name="uq_user_kind"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))  # asr | translate | enrich
    provider_id: Mapped[str] = mapped_column(String(64), default="mock")
    api_key: Mapped[str] = mapped_column(Text, default="")
    base_url: Mapped[str] = mapped_column(String(512), default="")
    model: Mapped[str] = mapped_column(String(128), default="")

    user: Mapped[User] = relationship(back_populates="providers")


class Media(Base):
    __tablename__ = "media"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(512))
    storage_key: Mapped[str] = mapped_column(String(512))
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    audio_storage_key: Mapped[str] = mapped_column(String(512), default="")
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    progress: Mapped[str] = mapped_column(String(255), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    asr_provider: Mapped[str] = mapped_column(String(64), default="mock")
    translate_provider: Mapped[str] = mapped_column(String(64), default="mock")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped[User] = relationship(back_populates="media")
    segments: Mapped[list[Segment]] = relationship(
        back_populates="media", order_by="Segment.idx", cascade="all, delete-orphan"
    )


class Segment(Base):
    __tablename__ = "segments"
    __table_args__ = (UniqueConstraint("media_id", "idx", name="uq_media_idx"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    media_id: Mapped[int] = mapped_column(ForeignKey("media.id"), index=True)
    idx: Mapped[int] = mapped_column(Integer)
    start_ms: Mapped[int] = mapped_column(Integer, default=0)
    end_ms: Mapped[int] = mapped_column(Integer, default=0)
    raw_en: Mapped[str] = mapped_column(Text, default="")
    raw_zh: Mapped[str] = mapped_column(Text, default="")
    edited_en: Mapped[str] = mapped_column(Text, default="")
    edited_zh: Mapped[str] = mapped_column(Text, default="")
    words_json: Mapped[str] = mapped_column(Text, default="[]")  # [{text,start_ms,end_ms}]

    media: Mapped[Media] = relationship(back_populates="segments")

    @property
    def text_en(self) -> str:
        return self.edited_en or self.raw_en

    @property
    def text_zh(self) -> str:
        return self.edited_zh or self.raw_zh


class Deck(Base):
    __tablename__ = "decks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(back_populates="decks")
    cards: Mapped[list[Card]] = relationship(back_populates="deck")


class Card(Base):
    __tablename__ = "cards"
    __table_args__ = (UniqueConstraint("user_id", "headword", name="uq_user_headword"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    deck_id: Mapped[int] = mapped_column(ForeignKey("decks.id"), index=True)
    card_type: Mapped[str] = mapped_column(String(16), default="word", index=True)
    headword: Mapped[str] = mapped_column(String(512), index=True)
    pos: Mapped[str] = mapped_column(String(32), default="")
    ipa: Mapped[str] = mapped_column(String(64), default="")
    meaning_zh: Mapped[str] = mapped_column(Text, default="")
    example_en: Mapped[str] = mapped_column(Text, default="")
    example_zh: Mapped[str] = mapped_column(Text, default="")
    media_id: Mapped[int | None] = mapped_column(ForeignKey("media.id"), nullable=True)
    segment_id: Mapped[int | None] = mapped_column(ForeignKey("segments.id"), nullable=True)
    t_ms: Mapped[int] = mapped_column(Integer, default=0)
    audio_clip_key: Mapped[str] = mapped_column(String(512), default="")
    tags: Mapped[str] = mapped_column(Text, default="")  # comma-separated

    # SRS (SM-2 compatible, FSRS-ready fields)
    state: Mapped[str] = mapped_column(String(16), default="new")
    stability: Mapped[float] = mapped_column(Float, default=0)
    difficulty: Mapped[float] = mapped_column(Float, default=0)
    ease: Mapped[float] = mapped_column(Float, default=2.5)
    interval_days: Mapped[float] = mapped_column(Float, default=0)
    reps: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    due_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    last_review_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    suspended: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    deck: Mapped[Deck] = relationship(back_populates="cards")


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), index=True)
    rating: Mapped[int] = mapped_column(Integer)  # 1..4
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    prev_state: Mapped[str] = mapped_column(String(16), default="")
    next_state: Mapped[str] = mapped_column(String(16), default="")


class GlossaryTerm(Base):
    __tablename__ = "glossary_terms"
    __table_args__ = (UniqueConstraint("user_id", "term", name="uq_user_term"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    term: Mapped[str] = mapped_column(String(128))
    keep_as: Mapped[str] = mapped_column(String(128), default="")
    note: Mapped[str] = mapped_column(Text, default="")


class Story(Base):
    """LLM-composed short story that weaves together one day's new words."""

    __tablename__ = "stories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    day: Mapped[str] = mapped_column(String(10), index=True)  # client-local YYYY-MM-DD
    words: Mapped[str] = mapped_column(Text, default="[]")  # JSON list of headwords
    content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
