import time
from pathlib import Path

import ctranslate2

print("ct2", ctranslate2.__version__, flush=True)
p = r"E:\leran-models\whisper\Systran__faster-whisper-base"
print("listdir", list(Path(p).iterdir())[:10], flush=True)
print("load Whisper engine...", flush=True)
t = time.time()
try:
    model = ctranslate2.models.Whisper(p, device="cpu", compute_type="int8")
    print("engine loaded", time.time() - t, flush=True)
except Exception as e:
    print("engine err", e, flush=True)
    raise
print("ok", flush=True)
