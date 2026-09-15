from __future__ import annotations

from datetime import datetime, timedelta

from ..models import Card


def schedule(card: Card, rating: int, now: datetime | None = None) -> Card:
    """SM-2 style scheduler. rating: 1=Again 2=Hard 3=Good 4=Easy."""
    now = now or datetime.utcnow()
    card.reps += 1
    card.last_review_at = now

    if rating == 1:
        card.lapses += 1
        card.state = "relearning"
        card.ease = max(1.3, card.ease - 0.2)
        card.interval_days = 0.01  # ~15 min
    elif card.state == "new":
        card.state = "learning"
        card.interval_days = 0.5 if rating >= 3 else 0.08
        if rating == 4:
            card.ease = min(3.0, card.ease + 0.15)
    else:
        if rating == 2:
            card.ease = max(1.3, card.ease - 0.15)
            card.interval_days = max(1.0, card.interval_days * 1.2)
        elif rating == 3:
            card.interval_days = max(1.0, card.interval_days * card.ease)
        else:
            card.ease = min(3.0, card.ease + 0.15)
            card.interval_days = max(1.0, card.interval_days * card.ease * 1.3)
        card.state = "review"

    # Keep FSRS-ish fields loosely in sync for a later swap.
    card.stability = max(card.stability, card.interval_days)
    card.difficulty = min(10.0, max(1.0, (3.0 - card.ease) * 3 + 3))
    card.due_at = now + timedelta(days=card.interval_days)
    return card


def preview_intervals(card: Card) -> list[float]:
    """Next interval (days) each rating would produce, without mutating the card.

    Mirrors schedule()'s math for the answer-button hints Anki shows
    ("15分 / 1.2天 / 3天 / 4天"). Order: [Again, Hard, Good, Easy].
    """
    out: list[float] = []
    for rating in (1, 2, 3, 4):
        if rating == 1:
            out.append(0.01)
        elif card.state == "new":
            out.append(0.5 if rating >= 3 else 0.08)
        elif rating == 2:
            out.append(max(1.0, card.interval_days * 1.2))
        elif rating == 3:
            out.append(max(1.0, card.interval_days * card.ease))
        else:
            out.append(max(1.0, card.interval_days * card.ease * 1.3))
    return out
