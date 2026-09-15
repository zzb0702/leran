"""Smoke test for Leran API — run from apps/api with venv python."""
from __future__ import annotations

import io
import sys
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"


def main() -> int:
    client = httpx.Client(base_url=BASE, timeout=30)

    # auth
    r = client.post("/api/auth/register", json={"email": "demo@leran.local", "password": "demo1234"})
    print("register", r.status_code, r.text[:120])
    r = client.post(
        "/api/auth/login",
        data={"username": "demo@leran.local", "password": "demo1234"},
    )
    print("login", r.status_code, r.text[:120])
    if r.status_code != 200:
        # debug hash
        from app.auth import hash_password, verify_password

        h = hash_password("demo1234")
        print("local verify", verify_password("demo1234", h))
        return 1
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # upload
    files = {"file": ("demo-clip.mp4", io.BytesIO(b"\x00" * 4096), "video/mp4")}
    r = client.post("/api/media/upload", headers=headers, files=files, data={"title": "GPU Throughput"})
    print("upload", r.status_code, r.text[:200])
    r.raise_for_status()
    media_id = r.json()["id"]

    import time

    for _ in range(10):
        m = client.get(f"/api/media/{media_id}", headers=headers).json()
        print("status", m["status"], m.get("error"))
        if m["status"] in {"ready", "failed"}:
            break
        time.sleep(0.3)

    segs = client.get(f"/api/media/{media_id}/segments", headers=headers).json()
    print("segments", len(segs))
    if not segs:
        print("NO_SEGMENTS")
        return 1

    card = client.post(
        "/api/cards/from-segment",
        headers=headers,
        json={"segment_id": segs[0]["id"], "headword": "throughput"},
    )
    print("card", card.status_code, card.text[:200])
    card.raise_for_status()

    queue = client.get("/api/review/queue", headers=headers).json()
    print("queue", len(queue))
    assert queue, "empty review queue"

    rev = client.post(
        f"/api/review/{queue[0]['card']['id']}",
        headers=headers,
        json={"rating": 3},
    )
    print("review", rev.status_code, rev.json().get("state"), rev.json().get("due_at"))

    exp = client.get(
        f"/api/media/{media_id}/export",
        params={"format": "srt", "lang": "bilingual"},
        headers=headers,
    )
    print("export", exp.status_code, "len", len(exp.text))
    print(exp.text[:180])

    today = client.get("/api/today", headers=headers).json()
    print("today", today)
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
