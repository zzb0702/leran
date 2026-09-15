import time

import httpx

c = httpx.Client(base_url="http://127.0.0.1:8000", timeout=60)
r = c.post("/api/auth/login", data={"username": "demo@leran.local", "password": "demo1234"})
h = {"Authorization": "Bearer " + r.json()["access_token"]}
m = c.post("/api/media/12/reprocess", headers=h, json={})
print("reprocess", m.status_code, m.json().get("status"), m.json().get("progress"))
for i in range(20):
    time.sleep(5)
    mm = c.get("/api/media/12", headers=h).json()
    segs = c.get("/api/media/12/segments", headers=h).json()
    zh = sum(1 for s in segs if s.get("text_zh"))
    print(f"{i} {mm['status']} | {mm.get('progress')} | segs={len(segs)} zh={zh}")
    if mm["status"] in ("ready", "failed"):
        print("error", (mm.get("error") or "")[:240])
        break
