"""Verify chunked upload + extract_audio status + range playback."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
CHUNK = 256 * 1024  # small chunks for test


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=120)
    r = c.post("/api/auth/login", data={"username": "demo@leran.local", "password": "demo1234"})
    r.raise_for_status()
    h = {"Authorization": "Bearer " + r.json()["access_token"]}

    limits = c.get("/api/media/limits", headers=h).json()
    print("limits", limits["max_upload_mb"], limits["chunk_size_mb"])

    # Build ~600KB fake file by repeating mp3-like header bytes (or real tone if present)
    tone = Path(r"data\demo-tone.mp3")
    if tone.exists():
        payload = tone.read_bytes() * 20  # ~480KB
    else:
        payload = b"\x00" * (600 * 1024)
    src = Path(r"data\chunk-test.bin")
    src.write_bytes(payload)
    print("payload", len(payload))

    total_chunks = (len(payload) + CHUNK - 1) // CHUNK
    init = c.post(
        "/api/media/upload/init",
        headers=h,
        json={"upload_id": "", "index": 0, "total_chunks": total_chunks, "total_size": len(payload)},
    )
    print("init", init.status_code, init.text[:120])
    init.raise_for_status()
    upload_id = init.json()["upload_id"]

    for i in range(total_chunks):
        part = payload[i * CHUNK : (i + 1) * CHUNK]
        files = {"file": (f"chunk_{i}", part, "application/octet-stream")}
        data = {"upload_id": upload_id, "index": str(i)}
        up = c.post("/api/media/upload/chunk", headers=h, data=data, files=files)
        if up.status_code != 200:
            print("chunk fail", i, up.status_code, up.text)
            return 1
        print("chunk", i + 1, "/", total_chunks, up.json())

    done = c.post(
        "/api/media/upload/complete",
        headers=h,
        json={
            "upload_id": upload_id,
            "filename": "chunk-demo.mp3",
            "title": "Chunk Demo",
            "total_size": len(payload),
        },
    )
    print("complete", done.status_code, done.text[:200])
    done.raise_for_status()
    media_id = done.json()["id"]

    for _ in range(20):
        m = c.get(f"/api/media/{media_id}", headers=h).json()
        print("status", m["status"], "err", m.get("error"), "size", m.get("file_size"), "dur", m.get("duration_ms"))
        if m["status"] in ("ready", "failed"):
            break
        time.sleep(0.4)

    # Range request
    rng = c.get(f"/api/media/{media_id}/file", headers={**h, "Range": "bytes=0-99"})
    print("range", rng.status_code, len(rng.content), rng.headers.get("content-range"))

    segs = c.get(f"/api/media/{media_id}/segments", headers=h).json()
    print("segs", len(segs))
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
