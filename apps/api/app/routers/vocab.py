from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import settings
from ..db import get_db
from ..models import Card, Deck, Media, ProviderConfig, Review, Segment, User
from ..schemas import (
    CardCreate,
    CardFromSegment,
    CardOut,
    CardPatch,
    DeckCreate,
    DeckOut,
    ReviewQueueItem,
    ReviewSubmit,
    TodayStats,
    MediaOut,
    WeekStat,
)
from ..services.export_cards import (
    build_anki_zip,
    cards_to_anki_tsv,
    cards_to_csv,
    extract_audio_clip,
    ffmpeg_bin,
)
from ..services.providers import resolve_enrich
from ..services.srs import preview_intervals, schedule

router = APIRouter(prefix="/api", tags=["vocab"])


def _default_deck(db: Session, user: User) -> Deck:
    deck = (
        db.query(Deck)
        .filter(Deck.user_id == user.id, Deck.is_default.is_(True))
        .first()
    )
    if deck:
        return deck
    deck = Deck(user_id=user.id, name="视频收集", description="从字幕入卡", is_default=True)
    db.add(deck)
    db.commit()
    db.refresh(deck)
    return deck


@router.get("/lookup/word")
def lookup_word(
    word: str,
    segment_id: int | None = None,
    deep: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Hover dictionary: card → cache → ECDICT → free dict API → (optional) LLM enrich."""
    from ..services.dict_api import (
        fetch_baidu,
        fetch_free_dictionary,
        fetch_youdao,
        get_cached,
        put_cached,
    )
    from ..services import ecdict as ecdict_service

    headword = (word or "").strip().strip(".,!?;:\"'()[]").lower()
    if not headword or len(headword) > 64:
        raise HTTPException(status_code=400, detail="Invalid word")

    sentence = ""
    if segment_id:
        seg = db.get(Segment, segment_id)
        if seg:
            sentence = seg.text_en

    def _pack(**kwargs) -> dict:
        base = {
            "word": headword,
            "ipa": "",
            "pos": "",
            "meaning_zh": "",
            "meaning_en": "",
            "example_en": sentence,
            "example_zh": "",
            "in_card": False,
            "card_id": None,
            "source": "",
        }
        base.update(kwargs)
        return base

    card = (
        db.query(Card)
        .filter(
            Card.user_id == user.id,
            Card.card_type == "word",
            Card.headword == headword,
        )
        .first()
    )
    if card and card.meaning_zh:
        return _pack(
            ipa=card.ipa,
            pos=card.pos,
            meaning_zh=card.meaning_zh,
            example_en=card.example_en or sentence,
            example_zh=card.example_zh,
            in_card=True,
            card_id=card.id,
            source="card",
        )

    # 1) disk/memory cache — usually <5ms
    cached = get_cached(headword)
    if cached and not deep:
        return _pack(**{k: cached.get(k, "") for k in (
            "ipa", "pos", "meaning_zh", "meaning_en", "example_en", "example_zh"
        )}, source=cached.get("source") or "cache")

    # 2) mock lexicon (instant)
    from ..services.providers.mock import _MOCK_LEXICON

    hit = _MOCK_LEXICON.get(headword)
    if hit and not deep:
        payload = _pack(
            ipa=hit["ipa"],
            pos=hit["pos"],
            meaning_zh=hit["meaning_zh"],
            source="lexicon",
        )
        put_cached(headword, payload)
        return payload

    # 3) offline ECDICT sqlite — local ms-level, works with no network/key
    local = ecdict_service.lookup(headword)
    if local and not deep:
        payload = _pack(
            ipa=local.get("ipa") or "",
            pos=local.get("pos") or "",
            meaning_zh=local.get("meaning_zh") or "",
            meaning_en=local.get("meaning_en") or "",
            example_en=sentence,
            source="ecdict",
        )
        put_cached(headword, payload)
        return payload

    # 4) Youdao (fast in CN, ~300ms) → Baidu (keyed official fallback) → English-only API
    free = fetch_youdao(headword)
    if not free:
        dcfg = (
            db.query(ProviderConfig)
            .filter(ProviderConfig.user_id == user.id, ProviderConfig.kind == "dict")
            .first()
        )
        if dcfg and dcfg.provider_id == "baidu":
            free = fetch_baidu(headword, dcfg.model or "", dcfg.api_key or "")
    if not free and deep:
        free = fetch_free_dictionary(headword)
    if free:
        meaning_zh = free.get("meaning_zh") or ""
        if deep and not meaning_zh:
            try:
                enrich = resolve_enrich(db, user)
                draft = enrich.define_in_context(headword, sentence)
                meaning_zh = draft.get("meaning_zh") or ""
            except Exception:  # noqa: BLE001
                meaning_zh = ""
        payload = _pack(
            ipa=free.get("ipa") or "",
            pos=free.get("pos") or "",
            meaning_en=free.get("meaning_en") or "",
            meaning_zh=meaning_zh,
            example_en=free.get("example_en") or sentence,
            source=free.get("source") or "dict",
        )
        put_cached(headword, payload)
        return payload

    # 5) LLM only on deep request (hover never waits for LLM)
    if deep:
        try:
            enrich = resolve_enrich(db, user)
            draft = enrich.define_in_context(headword, sentence)
            payload = _pack(
                ipa=draft.get("ipa") or "",
                pos=draft.get("pos") or "",
                meaning_zh=draft.get("meaning_zh") or "",
                example_en=draft.get("example_en") or sentence,
                example_zh=draft.get("example_zh") or "",
                source="enrich",
            )
            put_cached(headword, payload)
            return payload
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"词典查询失败: {exc}") from exc

    return _pack(source="none")


@router.get("/graph/word")
def graph_word(
    word: str,
    user: User = Depends(get_current_user),
) -> dict:
    """Offline word knowledge graph: inflections / family / roots / confusables."""
    from ..services import word_graph

    data = word_graph.build_graph(word)
    if not data:
        raise HTTPException(status_code=404, detail="ECDICT 中没有这个词（或词库未配置）")
    return data


@router.get("/today", response_model=TodayStats)
def today_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TodayStats:
    now = datetime.utcnow()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    q = db.query(Card).filter(Card.user_id == user.id, Card.suspended.is_(False))
    due = q.filter(Card.due_at <= now, Card.state != "new").count()
    new = q.filter(Card.state == "new").count()
    learning = q.filter(Card.state.in_(["learning", "relearning"])).count()
    processing = (
        db.query(Media)
        .filter(Media.user_id == user.id, Media.status.notin_(["ready", "failed"]))
        .count()
    )
    ready = db.query(Media).filter(Media.user_id == user.id, Media.status == "ready").count()
    recent = (
        db.query(Media)
        .filter(Media.user_id == user.id)
        .order_by(Media.updated_at.desc())
        .limit(5)
        .all()
    )
    media_outs: list[MediaOut] = []
    for m in recent:
        seg_count = db.query(Segment).filter(Segment.media_id == m.id).count()
        card_count = db.query(Card).filter(Card.media_id == m.id).count()
        item = MediaOut.model_validate(m)
        item.segment_count = seg_count
        item.card_count = card_count
        media_outs.append(item)

    reviews_today = (
        db.query(Review)
        .join(Card, Review.card_id == Card.id)
        .filter(Card.user_id == user.id, Review.reviewed_at >= day_start)
        .count()
    )

    week: list[WeekStat] = []
    for offset in range(6, -1, -1):
        d_start = day_start - timedelta(days=offset)
        d_end = d_start + timedelta(days=1)
        new_words = (
            db.query(Card)
            .filter(
                Card.user_id == user.id,
                Card.card_type == "word",
                Card.created_at >= d_start,
                Card.created_at < d_end,
            )
            .count()
        )
        rows = (
            db.query(Review)
            .join(Card, Review.card_id == Card.id)
            .filter(
                Card.user_id == user.id,
                Review.reviewed_at >= d_start,
                Review.reviewed_at < d_end,
            )
            .with_entities(Review.duration_ms)
            .all()
        )
        minutes = round(sum(r[0] or 0 for r in rows) / 60000.0, 1)
        week.append(
            WeekStat(
                date=d_start.strftime("%Y-%m-%d"),
                new_words=new_words,
                reviews=len(rows),
                minutes=minutes,
            )
        )

    return TodayStats(
        due_count=due,
        new_count=new,
        learning_count=learning,
        media_processing=processing,
        media_ready=ready,
        recent_media=media_outs,
        reviews_today=reviews_today,
        week=week,
    )


@router.get("/decks", response_model=list[DeckOut])
def list_decks(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DeckOut]:
    _default_deck(db, user)
    decks = db.query(Deck).filter(Deck.user_id == user.id).all()
    out: list[DeckOut] = []
    for d in decks:
        count = db.query(Card).filter(Card.deck_id == d.id).count()
        item = DeckOut.model_validate(d)
        item.card_count = count
        out.append(item)
    return out


@router.post("/decks", response_model=DeckOut)
def create_deck(
    body: DeckCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DeckOut:
    deck = Deck(user_id=user.id, name=body.name, description=body.description)
    db.add(deck)
    db.commit()
    db.refresh(deck)
    item = DeckOut.model_validate(deck)
    item.card_count = 0
    return item


def _normalize_sentence(text: str) -> str:
    return " ".join((text or "").split())


def _clip_audio_for_card(db: Session, user: User, card: Card) -> None:
    """Best-effort audio clip for review playback / Anki package."""
    if card.media_id is None or not ffmpeg_bin():
        return
    media = db.get(Media, card.media_id)
    seg = db.get(Segment, card.segment_id) if card.segment_id else None
    if not media or media.user_id != user.id:
        return
    end_ms = seg.end_ms if seg else card.t_ms + 2500
    clip = extract_audio_clip(media, card.t_ms, end_ms)
    if clip:
        card.audio_clip_key = str(clip.relative_to(settings.clip_dir)).replace("\\", "/")
        db.commit()
        db.refresh(card)


@router.get("/cards", response_model=list[CardOut])
def list_cards(
    deck_id: int | None = None,
    q: str = "",
    card_type: str = "",
    segment_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CardOut]:
    query = db.query(Card).filter(Card.user_id == user.id)
    if deck_id:
        query = query.filter(Card.deck_id == deck_id)
    if card_type:
        query = query.filter(Card.card_type == card_type)
    if segment_id:
        query = query.filter(Card.segment_id == segment_id)
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(
            (Card.headword.ilike(like))
            | (Card.meaning_zh.ilike(like))
            | (Card.example_en.ilike(like))
        )
    rows = query.order_by(Card.updated_at.desc()).limit(500).all()
    return [CardOut.model_validate(c) for c in rows]


@router.post("/cards", response_model=CardOut)
def create_card(
    body: CardCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CardOut:
    card_type = "sentence" if body.card_type == "sentence" else "word"
    if card_type == "sentence":
        headword = _normalize_sentence(body.headword)
        match_headword = headword.lower()
    else:
        headword = body.headword.strip().lower()
        match_headword = headword
    if not headword:
        raise HTTPException(status_code=400, detail="headword required")
    if card_type == "sentence" and len(headword) > 500:
        raise HTTPException(status_code=400, detail="句子过长（>500字符）")

    existing = (
        db.query(Card)
        .filter(
            Card.user_id == user.id,
            Card.card_type == card_type,
            Card.headword.ilike(match_headword),
        )
        .first()
    )
    if existing:
        if body.example_en and not existing.example_en:
            existing.example_en = body.example_en
        if body.example_zh and not existing.example_zh:
            existing.example_zh = body.example_zh
        if body.meaning_zh and not existing.meaning_zh:
            existing.meaning_zh = body.meaning_zh
        if body.segment_id and not existing.segment_id:
            existing.segment_id = body.segment_id
            existing.media_id = body.media_id
            existing.t_ms = body.t_ms
        db.commit()
        db.refresh(existing)
        return CardOut.model_validate(existing)

    deck_id = body.deck_id
    if not deck_id:
        deck_id = _default_deck(db, user).id
    card = Card(
        user_id=user.id,
        deck_id=deck_id,
        card_type=card_type,
        headword=headword,
        pos=body.pos,
        meaning_zh=body.meaning_zh,
        example_en=body.example_en or (headword if card_type == "sentence" else ""),
        example_zh=body.example_zh,
        media_id=body.media_id,
        segment_id=body.segment_id,
        t_ms=body.t_ms,
        state="new",
        due_at=datetime.utcnow(),
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    _clip_audio_for_card(db, user, card)
    return CardOut.model_validate(card)


@router.post("/cards/from-segment", response_model=CardOut)
def card_from_segment(
    body: CardFromSegment,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CardOut:
    seg = db.get(Segment, body.segment_id)
    if not seg:
        raise HTTPException(status_code=404, detail="Segment not found")
    media = db.get(Media, seg.media_id)
    if not media or media.user_id != user.id:
        raise HTTPException(status_code=404, detail="Segment not found")

    if body.card_type == "sentence":
        headword = _normalize_sentence(seg.text_en)
        meaning = body.meaning_zh.strip() or seg.text_zh
        return create_card(
            CardCreate(
                headword=headword,
                card_type="sentence",
                meaning_zh=meaning,
                example_en=seg.text_en,
                example_zh=seg.text_zh,
                media_id=seg.media_id,
                segment_id=seg.id,
                t_ms=seg.start_ms,
            ),
            db=db,
            user=user,
        )

    headword = body.headword.strip().lower()
    meaning = body.meaning_zh
    pos = body.pos
    if not headword:
        raise HTTPException(status_code=400, detail="headword required")
    if not meaning:
        try:
            enrich = resolve_enrich(db, user)
            draft = enrich.define_in_context(headword, seg.text_en)
            meaning = draft.get("meaning_zh") or f"（语境义）{headword}"
            pos = pos or draft.get("pos") or ""
        except Exception:  # noqa: BLE001
            meaning = f"（语境义）{headword}"

    return create_card(
        CardCreate(
            headword=headword,
            card_type="word",
            meaning_zh=meaning,
            pos=pos,
            example_en=seg.text_en,
            example_zh=seg.text_zh,
            media_id=seg.media_id,
            segment_id=seg.id,
            t_ms=seg.start_ms,
        ),
        db=db,
        user=user,
    )


@router.patch("/cards/{card_id}", response_model=CardOut)
def patch_card(
    card_id: int,
    body: CardPatch,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CardOut:
    card = db.get(Card, card_id)
    if not card or card.user_id != user.id:
        raise HTTPException(status_code=404, detail="Card not found")
    if body.meaning_zh is not None:
        card.meaning_zh = body.meaning_zh
    if body.example_en is not None:
        card.example_en = body.example_en
    if body.example_zh is not None:
        card.example_zh = body.example_zh
    if body.suspended is not None:
        card.suspended = body.suspended
    if body.deck_id is not None:
        card.deck_id = body.deck_id
    db.commit()
    db.refresh(card)
    return CardOut.model_validate(card)


@router.delete("/cards/{card_id}")
def delete_card(
    card_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    card = db.get(Card, card_id)
    if not card or card.user_id != user.id:
        raise HTTPException(status_code=404, detail="Card not found")
    db.delete(card)
    db.commit()
    return {"ok": True}


@router.get("/review/queue", response_model=list[ReviewQueueItem])
def review_queue(
    deck_id: int | None = None,
    limit: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ReviewQueueItem]:
    now = datetime.utcnow()
    query = db.query(Card).filter(
        Card.user_id == user.id,
        Card.suspended.is_(False),
        (Card.state == "new") | (Card.due_at <= now),
    )
    if deck_id:
        query = query.filter(Card.deck_id == deck_id)
    # Prefer due review over new.
    rows = query.order_by(Card.state.desc(), Card.due_at.asc()).limit(limit).all()
    rows.sort(key=lambda c: (0 if c.state != "new" else 1, c.due_at))
    items: list[ReviewQueueItem] = []
    for c in rows:
        items.append(
            ReviewQueueItem(
                card=CardOut.model_validate(c),
                media_id=c.media_id,
                t_ms=c.t_ms,
                interval_previews=preview_intervals(c),
            )
        )
    return items


@router.post("/review/{card_id}", response_model=CardOut)
def submit_review(
    card_id: int,
    body: ReviewSubmit,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CardOut:
    card = db.get(Card, card_id)
    if not card or card.user_id != user.id:
        raise HTTPException(status_code=404, detail="Card not found")
    prev_state = card.state
    schedule(card, body.rating)
    review = Review(
        card_id=card.id,
        rating=body.rating,
        duration_ms=body.duration_ms,
        prev_state=prev_state,
        next_state=card.state,
    )
    db.add(review)
    db.commit()
    db.refresh(card)
    return CardOut.model_validate(card)


@router.get("/export/cards.csv")
def export_cards_csv(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    cards = (
        db.query(Card)
        .filter(Card.user_id == user.id)
        .order_by(Card.created_at.desc())
        .all()
    )
    return Response(
        cards_to_csv(cards),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="leran_cards.csv"'},
    )


@router.get("/export/anki.tsv")
def export_anki_tsv(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    cards = (
        db.query(Card)
        .filter(Card.user_id == user.id)
        .order_by(Card.created_at.desc())
        .all()
    )
    return Response(
        cards_to_anki_tsv(cards),
        media_type="text/tab-separated-values; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="leran_cards.tsv"'},
    )


@router.get("/export/anki.zip")
def export_anki_zip(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    cards = (
        db.query(Card)
        .filter(Card.user_id == user.id)
        .order_by(Card.created_at.desc())
        .all()
    )
    clips: dict[int, Path] = {}
    for c in cards:
        if c.audio_clip_key:
            p = settings.clip_dir / c.audio_clip_key
            if p.exists():
                clips[c.id] = p
    payload = build_anki_zip(cards, clips)
    return Response(
        payload,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="leran_anki.zip"'},
    )


@router.get("/cards/{card_id}/audio")
def card_audio(
    card_id: int,
    request: Request,
    token: str = "",
    db: Session = Depends(get_db),
):
    from fastapi.responses import FileResponse
    from jose import JWTError, jwt

    from ..config import settings as app_settings

    raw = token
    if not raw:
        auth = request.headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            raw = auth[7:].strip()

    user = None
    if raw:
        try:
            payload = jwt.decode(raw, app_settings.secret_key, algorithms=["HS256"])
            user = db.get(User, int(payload.get("sub")))
        except (JWTError, TypeError, ValueError):
            user = None
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    card = db.get(Card, card_id)
    if not card or card.user_id != user.id or not card.audio_clip_key:
        raise HTTPException(status_code=404, detail="Audio not found")
    path = settings.clip_dir / card.audio_clip_key
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio missing")
    return FileResponse(path, media_type="audio/mpeg")
