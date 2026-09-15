import time
from pathlib import Path

import ctranslate2

print("ct2", ctranslate2.__version__, flush=True)
from faster_whisper import WhisperModel

p = r"E:\leran-models\whisper\deepdml__faster-whisper-large-v3-turbo-ct2"
print("load turbo...", flush=True)
t = time.time()
m = WhisperModel(p, device="cpu", compute_type="int8", cpu_threads=8)
print("loaded", round(time.time() - t, 2), flush=True)

audio = r"data\speech-sample.wav"
t = time.time()
segs, info = m.transcribe(
    audio, language="en", beam_size=1, word_timestamps=True, vad_filter=True
)
lines = []
for s in segs:
    line = f"[{s.start:.2f}-{s.end:.2f}] {s.text.strip()}"
    print(line, flush=True)
    lines.append(line)
el = time.time() - t
summary = f"elapsed={el:.2f} audio={info.duration:.2f} rtf={el/max(info.duration,0.01):.3f} n={len(lines)}"
print(summary, flush=True)
Path(r"E:\leran-models\asr_result.txt").write_text(
    "\n".join(lines) + "\n" + summary + "\n", encoding="utf-8"
)
print("done", flush=True)
