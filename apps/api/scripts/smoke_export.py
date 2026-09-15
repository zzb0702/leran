"""Smoke test card export + optional audio clip."""
from __future__ import annotations

import sys

import httpx

BASE = "http://127.0.0.1:8000"


def main() -> int:
    client = httpx.Client(base_url=BASE, timeout=30)
    r = client.post(
        "/api/auth/login",
        data={"username": "demo@leran.local", "password": "demo1234"},
    )
    r.raise_for_status()
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    cards = client.get("/api/cards", headers=h).json()
    print("cards", len(cards))
    if cards:
        print("audio_clip_key", cards[0].get("audio_clip_key"))

    for path, name in [
        ("/api/export/cards.csv", "csv"),
        ("/api/export/anki.tsv", "tsv"),
        ("/api/export/anki.zip", "zip"),
    ]:
        res = client.get(path, headers=h)
        print(name, res.status_code, len(res.content), res.headers.get("content-type"))

    # mine another card to trigger clip extraction
    segs = client.get("/api/media/1/segments", headers=h).json()
    if segs:
        card = client.post(
            "/api/cards/from-segment",
            headers=h,
            json={"segment_id": segs[min(1, len(segs) - 1)]["id"], "headword": "bandwidth"},
        )
        print("new_card", card.status_code, card.json().get("audio_clip_key"))
        if card.json().get("audio_clip_key"):
            audio = client.get(f"/api/cards/{card.json()['id']}/audio", headers=h)
            print("audio", audio.status_code, len(audio.content))

    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
