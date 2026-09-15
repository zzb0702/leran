from pathlib import Path

import httpx

c = httpx.Client(base_url="http://127.0.0.1:8000", timeout=60)
r = c.post("/api/auth/login", data={"username": "demo@leran.local", "password": "demo1234"})
r.raise_for_status()
h = {"Authorization": "Bearer " + r.json()["access_token"]}

mp3 = Path(r"data\demo-tone.mp3")
files = {"file": ("demo-tone.mp3", mp3.read_bytes(), "audio/mpeg")}
m = c.post("/api/media/upload", headers=h, files=files, data={"title": "Tone Demo"}).json()
print("media", m["id"], m["status"])

import time

for _ in range(10):
    mm = c.get(f"/api/media/{m['id']}", headers=h).json()
    if mm["status"] in ("ready", "failed"):
        print("status", mm["status"], mm.get("error"))
        break
    time.sleep(0.3)

segs = c.get(f"/api/media/{m['id']}/segments", headers=h).json()
print("segs", len(segs), segs[0]["text_en"][:50] if segs else "")

card = c.post(
    "/api/cards/from-segment",
    headers=h,
    json={"segment_id": segs[0]["id"], "headword": "sine"},
).json()
print("card", card.get("id"), "clip", repr(card.get("audio_clip_key")))
if card.get("audio_clip_key"):
    a = c.get(f"/api/cards/{card['id']}/audio", headers=h)
    print("audio", a.status_code, len(a.content))
else:
    # debug ffmpeg path from server settings
    from app.config import settings
    from app.services.export_cards import ffmpeg_bin, extract_audio_clip
    from app.db import SessionLocal
    from app.models import Media

    print("ffmpeg_bin", ffmpeg_bin())
    print("settings.ffmpeg_path", settings.ffmpeg_path)
    db = SessionLocal()
    media = db.get(Media, m["id"])
    seg = segs[0]
    clip = extract_audio_clip(media, seg["start_ms"], seg["end_ms"])
    print("extract", clip)

zipr = c.get("/api/export/anki.zip", headers=h)
print("zip", zipr.status_code, len(zipr.content))
