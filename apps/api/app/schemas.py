from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6)


class UserOut(BaseModel):
    id: int
    email: str

    model_config = {"from_attributes": True}


class ProviderConfigIn(BaseModel):
    kind: str
    provider_id: str = "mock"
    api_key: str = ""
    base_url: str = ""
    model: str = ""


class ProviderConfigOut(BaseModel):
    kind: str
    provider_id: str
    base_url: str
    model: str
    has_api_key: bool = False

    model_config = {"from_attributes": True}


class WordSpan(BaseModel):
    text: str
    start_ms: int
    end_ms: int


class SegmentOut(BaseModel):
    id: int
    media_id: int
    idx: int
    start_ms: int
    end_ms: int
    text_en: str
    text_zh: str
    raw_en: str
    raw_zh: str
    words: list[WordSpan] = []

    model_config = {"from_attributes": True}


class SegmentUpdate(BaseModel):
    edited_en: str | None = None
    edited_zh: str | None = None
    start_ms: int | None = None
    end_ms: int | None = None


class MediaPatch(BaseModel):
    title: str = Field(min_length=1, max_length=300)


class MediaOut(BaseModel):
    id: int
    title: str
    duration_ms: int
    file_size: int = 0
    status: str
    progress: str = ""
    error: str
    asr_provider: str
    translate_provider: str
    created_at: datetime
    updated_at: datetime
    segment_count: int = 0
    card_count: int = 0

    model_config = {"from_attributes": True}


class UploadInitOut(BaseModel):
    upload_id: str
    storage_key: str
    chunk_size_bytes: int
    max_upload_bytes: int


class UploadCompleteIn(BaseModel):
    upload_id: str
    filename: str
    title: str = ""
    asr_provider: str = ""
    translate_provider: str = ""
    total_size: int = 0


class MediaCreateOptions(BaseModel):
    title: str = ""
    asr_provider: str = ""
    translate_provider: str = ""


class DeckOut(BaseModel):
    id: int
    name: str
    description: str
    is_default: bool
    card_count: int = 0

    model_config = {"from_attributes": True}


class DeckCreate(BaseModel):
    name: str
    description: str = ""


class CardOut(BaseModel):
    id: int
    deck_id: int
    headword: str
    pos: str
    ipa: str
    meaning_zh: str
    example_en: str
    example_zh: str
    media_id: int | None
    segment_id: int | None
    t_ms: int
    audio_clip_key: str
    tags: str
    state: str
    due_at: datetime
    suspended: bool
    created_at: datetime
    interval_days: float = 0
    ease: float = 2.5
    lapses: int = 0
    reps: int = 0

    model_config = {"from_attributes": True}


class CardCreate(BaseModel):
    headword: str
    deck_id: int | None = None
    meaning_zh: str = ""
    example_en: str = ""
    example_zh: str = ""
    media_id: int | None = None
    segment_id: int | None = None
    t_ms: int = 0
    pos: str = ""


class CardFromSegment(BaseModel):
    segment_id: int
    headword: str
    meaning_zh: str = ""
    pos: str = ""


class CardPatch(BaseModel):
    meaning_zh: str | None = None
    example_en: str | None = None
    example_zh: str | None = None
    suspended: bool | None = None
    deck_id: int | None = None


class ReviewSubmit(BaseModel):
    rating: int = Field(ge=1, le=4)
    duration_ms: int = 0


class ReviewQueueItem(BaseModel):
    card: CardOut
    media_id: int | None = None
    t_ms: int = 0
    interval_previews: list[float] = []  # days, [Again, Hard, Good, Easy]


class WeekStat(BaseModel):
    date: str  # YYYY-MM-DD (UTC)
    new_words: int
    reviews: int
    minutes: float = 0


class TodayStats(BaseModel):
    due_count: int
    new_count: int
    learning_count: int
    media_processing: int
    media_ready: int
    recent_media: list[MediaOut]
    reviews_today: int = 0
    week: list[WeekStat] = []


class GlossaryIn(BaseModel):
    term: str
    keep_as: str = ""
    note: str = ""


class GlossaryOut(BaseModel):
    id: int
    term: str
    keep_as: str
    note: str

    model_config = {"from_attributes": True}
