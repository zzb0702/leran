from __future__ import annotations

import os
import sys
import tempfile

td = tempfile.mkdtemp(prefix="leran_test_")
db_path = os.path.join(td, "t.db")
os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from app.db import SessionLocal, init_db
from app.main import app
from app.models import Media, Segment, User

init_db()
c = TestClient(app)

r = c.post("/api/auth/register", json={"email": "t@t.com", "password": "pass123"})
print("register", r.status_code)
r = c.post("/api/auth/login", data={"username": "t@t.com", "password": "pass123"})
print("login", r.status_code)
tok = r.json()["access_token"]
h = {"Authorization": f"Bearer {tok}"}

db = SessionLocal()
u = db.query(User).first()
m = Media(user_id=u.id, title="demo", storage_key="x.mp4", status="ready")
db.add(m)
db.commit()
db.refresh(m)
seg = Segment(
    media_id=m.id,
    idx=0,
    start_ms=1000,
    end_ms=3000,
    raw_en="This is a lovely sentence.",
    raw_zh="这是一句可爱的话.",
)
db.add(seg)
db.commit()
db.refresh(seg)

r = c.post("/api/cards/from-segment", headers=h, json={"segment_id": seg.id, "card_type": "sentence"})
print("sentence card", r.status_code, r.json().get("card_type"), r.json().get("headword"), r.json().get("meaning_zh"))
assert r.status_code == 200
assert r.json()["card_type"] == "sentence"
assert r.json()["headword"] == "This is a lovely sentence."
assert r.json()["meaning_zh"] == "这是一句可爱的话."

r2 = c.post("/api/cards/from-segment", headers=h, json={"segment_id": seg.id, "card_type": "sentence"})
print("dedup", r2.status_code, r2.json()["id"])
assert r.json()["id"] == r2.json()["id"]

r3 = c.post("/api/cards/from-segment", headers=h, json={"segment_id": seg.id, "headword": "lovely"})
print("word card", r3.status_code, r3.json()["card_type"], r3.json()["headword"])
assert r3.json()["card_type"] == "word"

r4 = c.get("/api/cards?card_type=sentence", headers=h)
print("list sentences", r4.status_code, len(r4.json()))
assert len(r4.json()) == 1

r5 = c.get("/api/cards?card_type=word", headers=h)
print("list words", r5.status_code, len(r5.json()))
assert len(r5.json()) == 1

r6 = c.get("/api/cards?q=lovely", headers=h)
print("search", r6.status_code, [x["card_type"] for x in r6.json()])
assert {x["card_type"] for x in r6.json()} == {"word", "sentence"}

print("ALL PASS")
