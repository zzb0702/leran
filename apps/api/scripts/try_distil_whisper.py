"""Download / load Distil-Whisper (or fallback) via faster-whisper on this machine."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Prefer China-friendly HF mirror when set by caller.
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HOME", r"E:\leran-models\hf")

from faster_whisper import WhisperModel

DOWNLOAD_ROOT = Path(r"E:\leran-models\whisper")
DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)

# Candidates: Distil first, then turbo CT2, then standard large-v3 CT2.
CANDIDATES = [
    "distil-whisper/distil-large-v3",
    "deepdml/faster-whisper-large-v3-turbo-ct2",
    "Systran/faster-whisper-large-v3",
]


def load_first_working():
    last_err = None
    for name in CANDIDATES:
        print(f"=== trying {name} ===", flush=True)
        t0 = time.time()
        try:
            model = WhisperModel(
                name,
                device="cuda",
                compute_type="float16",
                download_root=str(DOWNLOAD_ROOT),
            )
            print(f"LOADED {name} in {time.time() - t0:.1f}s cuda fp16", flush=True)
            return name, model
        except Exception as e:  # noqa: BLE001
            print(f"cuda/fp16 fail: {type(e).__name__}: {e}", flush=True)
            last_err = e
            try:
                model = WhisperModel(
                    name,
                    device="cpu",
                    compute_type="int8",
                    download_root=str(DOWNLOAD_ROOT),
                )
                print(f"LOADED {name} cpu int8 in {time.time() - t0:.1f}s", flush=True)
                return name, model
            except Exception as e2:  # noqa: BLE001
                print(f"cpu fail: {type(e2).__name__}: {e2}", flush=True)
                last_err = e2
    raise SystemExit(f"No model loaded. Last error: {last_err}")


def transcribe_demo(model, path: Path):
    t0 = time.time()
    segments, info = model.transcribe(
        str(path),
        language="en",
        word_timestamps=True,
        vad_filter=True,
        beam_size=5,
    )
    texts = []
    n = 0
    last_end = 0
    for seg in segments:
        n += 1
        last_end = seg.end
        if n <= 8:
            print(f"  [{seg.start:7.2f}-{seg.end:7.2f}] {seg.text.strip()}")
        texts.append(seg.text.strip())
    print(
        f"segments={n} last_end={last_end:.1f}s duration={getattr(info, 'duration', '?')}"
        f" elapsed={time.time() - t0:.1f}s"
    )
    return n, last_end, time.time() - t0


def main() -> int:
    audio = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        r"data\demo-tone.mp3"
    )
    if not audio.exists():
        print("missing", audio)
        return 1
    print("audio", audio, "size_mb", round(audio.stat().st_size / 1024 / 1024, 2))
    name, model = load_first_working()
    print("USING", name)
    transcribe_demo(model, audio)
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
