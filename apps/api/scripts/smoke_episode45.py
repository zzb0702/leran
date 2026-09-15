"""Process a ~45 minute audio through the full pipeline (mock providers)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
AUDIO = Path(r"data\episode-45min.mp3")


def main() -> int:
    if not AUDIO.exists():
        print("missing audio", AUDIO)
        return 1

    c = httpx.Client(base_url=BASE, timeout=300)
    r = c.post("/api/auth/login", data={"username": "demo@leran.local", "password": "demo1234"})
    r.raise_for_status()
    h = {"Authorization": "Bearer " + r.json()["access_token"]}

    print("uploading", AUDIO.stat().st_size, "bytes")
    files = {"file": (AUDIO.name, AUDIO.read_bytes(), "audio/mpeg")}
    m = c.post(
        "/api/media/upload",
        headers=h,
        files=files,
        data={"title": "Episode 45min", "asr_provider": "mock", "translate_provider": "mock"},
    )
    print("upload", m.status_code)
    m.raise_for_status()
    media_id = m.json()["id"]

    t0 = time.time()
    last = ""
    for i in range(120):
        mm = c.get(f"/api/media/{media_id}", headers=h).json()
        line = f"{mm['status']} | {mm.get('progress','')} | dur={mm.get('duration_ms')} segs={mm.get('segment_count')}"
        if line != last:
            print(f"[{time.time()-t0:5.1f}s] {line}")
            last = line
        if mm["status"] in ("ready", "failed"):
            print("final", mm["status"], mm.get("error"))
            if mm["status"] == "failed":
                return 1
            break
        time.sleep(0.5)
    else:
        print("TIMEOUT waiting for pipeline")
        return 1

    segs = c.get(f"/api/media/{media_id}/segments", headers=h).json()
    print("segments", len(segs))
    if segs:
        print("first", segs[0]["start_ms"], segs[0]["text_en"][:60])
        print("last", segs[-1]["start_ms"], segs[-1]["end_ms"], segs[-1]["text_en"][:60])
        # ensure times span close to 45 min
        span_min = segs[-1]["end_ms"] / 60000
        print("span_minutes", round(span_min, 2))
        if span_min < 40:
            print("WARN: span much shorter than episode")

    # range on large-ish file
    rng = c.get(f"/api/media/{media_id}/file", headers={**h, "Range": "bytes=1000-1999"})
    print("range", rng.status_code, len(rng.content))
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
