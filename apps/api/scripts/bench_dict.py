import time

import httpx

c = httpx.Client(base_url="http://127.0.0.1:8000", timeout=30)
r = c.post("/api/auth/login", data={"username": "demo@leran.local", "password": "demo1234"})
h = {"Authorization": "Bearer " + r.json()["access_token"]}
for w in ["throughput", "summer", "Northeast", "bottleneck", "suite"]:
    t = time.time()
    j = c.get("/api/lookup/word", params={"word": w}, headers=h).json()
    ms = int((time.time() - t) * 1000)
    print(w, ms, "ms", j.get("source"), "|", (j.get("meaning_zh") or j.get("meaning_en") or "")[:50])
t = time.time()
j = c.get("/api/lookup/word", params={"word": "throughput"}, headers=h).json()
print("cached", int((time.time() - t) * 1000), "ms", j.get("source"))
