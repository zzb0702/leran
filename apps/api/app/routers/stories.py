from __future__ import annotations

import json
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import get_db
from ..models import Story, User
from ..services.providers import resolve_enrich

router = APIRouter(prefix="/api/stories", tags=["stories"])

_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class StoryCreate(BaseModel):
    day: str = Field(min_length=10, max_length=10)
    words: list[str] = Field(min_length=1, max_length=30)


class StoryOut(BaseModel):
    id: int
    day: str
    words: list[str]
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


def _load_words(raw: str) -> list[str]:
    try:
        data = json.loads(raw)
        return [str(w) for w in data] if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


@router.post("", response_model=StoryOut)
def create_story(
    body: StoryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StoryOut:
    if not _DAY_RE.match(body.day):
        raise HTTPException(status_code=400, detail="Invalid day (expected YYYY-MM-DD)")
    words = list(dict.fromkeys(w.strip().lower() for w in body.words if w.strip()))[:20]
    if not words:
        raise HTTPException(status_code=400, detail="No valid words")

    try:
        enrich = resolve_enrich(db, user)
        content = enrich.compose_story(words)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"作文生成失败: {exc}") from exc

    story = Story(
        user_id=user.id,
        day=body.day,
        words=json.dumps(words, ensure_ascii=False),
        content=content,
    )
    db.add(story)
    db.commit()
    db.refresh(story)
    return StoryOut(
        id=story.id,
        day=story.day,
        words=words,
        content=story.content,
        created_at=story.created_at,
    )


@router.get("", response_model=list[StoryOut])
def list_stories(
    day: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[StoryOut]:
    q = db.query(Story).filter(Story.user_id == user.id)
    if day:
        q = q.filter(Story.day == day)
    rows = q.order_by(Story.created_at.desc(), Story.id.desc()).limit(100).all()
    return [
        StoryOut(
            id=s.id,
            day=s.day,
            words=_load_words(s.words),
            content=s.content,
            created_at=s.created_at,
        )
        for s in rows
    ]


@router.delete("/{story_id}")
def delete_story(
    story_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    story = db.get(Story, story_id)
    if not story or story.user_id != user.id:
        raise HTTPException(status_code=404, detail="Story not found")
    db.delete(story)
    db.commit()
    return {"ok": True}
