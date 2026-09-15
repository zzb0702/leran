"""E2E: upload speech sample with local-whisper (turbo CT2)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
AUDIO = Path(r"data\speech-sample.wav")


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=600)
    r = c.post("/api/auth/login", data={"username": "demo@leran.local", "password": "demo1234"})
    r.raise_for_status()
    h = {"Authorization": "Bearer " + r.json()["access_token"]}

    files = {"file": (AUDIO.name, AUDIO.read_bytes(), "audio/wav")}
    m = c.post(
        "/api/media/upload",
        headers=h,
        files=files,
        data={
            "title": "Speech Sample Distil",
            "asr_provider": "local-whisper",
            "translate_provider": "mock",
        },
    )
    print("upload", m.status_code, m.text[:200])
    m.raise_for_status()
    mid = m.json()["id"]

    t0 = time.time()
    for _ in range(60):
        mm = c.get(f"/api/media/{mid}", headers=h).json()
        print(f"{time.time()-t0:5.1f}s {mm['status']} {mm.get('progress','')} err={mm.get('error','')[:120]}")
        if mm["status"] in ("ready", "failed"):
            break
        time.sleep(1)
    else:
        print("TIMEOUT")
        return 1

    if mm["status"] != "ready":
        print("FAILED", mm.get("error"))
        return 1

    segs = c.get(f"/api/media/{mid}/segments", headers=h).json()
    print("segments", len(segs))
    for s in segs:
        print(f"  {s['start_ms']}-{s['end_ms']} EN={s['text_en']}")
        print(f"           ZH={s['text_zh']}")
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
