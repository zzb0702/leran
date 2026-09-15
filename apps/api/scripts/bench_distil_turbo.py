"""Load local CT2 turbo model (Distil-class speed) and transcribe a speech sample."""
from __future__ import annotations

import time
from pathlib import Path

from faster_whisper import WhisperModel

MODEL_DIR = Path(r"E:\leran-models\whisper\deepdml__faster-whisper-large-v3-turbo-ct2")
AUDIO = Path(r"data\speech-sample.wav")
OUT = Path(r"data\speech-sample.txt")


def main() -> int:
    print("model", MODEL_DIR, "exists", MODEL_DIR.exists())
    print("audio", AUDIO, "exists", AUDIO.exists(), "mb", round(AUDIO.stat().st_size/1024/1024, 2) if AUDIO.exists() else 0)
    if not MODEL_DIR.exists() or not AUDIO.exists():
        return 1

    t0 = time.time()
    device, compute = "cuda", "float16"
    try:
        model = WhisperModel(str(MODEL_DIR), device=device, compute_type=compute)
        print(f"LOAD {device}/{compute} {time.time()-t0:.1f}s")
    except Exception as e:  # noqa: BLE001
        print(f"cuda fail: {e}")
        t0 = time.time()
        model = WhisperModel(str(MODEL_DIR), device="cpu", compute_type="int8")
        device, compute = "cpu", "int8"
        print(f"LOAD cpu/int8 {time.time()-t0:.1f}s")

    t1 = time.time()
    segments, info = model.transcribe(
        str(AUDIO),
        language="en",
        word_timestamps=True,
        vad_filter=True,
        beam_size=5,
    )
    lines = []
    nwords = 0
    for seg in segments:
        line = f"[{seg.start:6.2f}-{seg.end:6.2f}] {seg.text.strip()}"
        print(line)
        lines.append(line)
        nwords += sum(1 for w in (seg.words or []) if w.word.strip())
    elapsed = time.time() - t1
    print(f"device={device} segments={len(lines)} words={nwords} asr_elapsed={elapsed:.2f}s")
    if info.duration:
        print(f"audio_duration={info.duration:.2f}s rtf={elapsed/max(info.duration,0.01):.3f}")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("wrote", OUT)
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
