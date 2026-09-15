"""Diagnose ctranslate2 CUDA and load model with explicit errors."""
from __future__ import annotations

import traceback
from pathlib import Path

MODEL_DIR = Path(r"E:\leran-models\whisper\deepdml__faster-whisper-large-v3-turbo-ct2")


def main() -> int:
    print("import ctranslate2", flush=True)
    try:
        import ctranslate2

        print("ct2", ctranslate2.__version__, flush=True)
        try:
            print("cuda count", ctranslate2.get_cuda_device_count(), flush=True)
        except Exception:
            traceback.print_exc()
    except Exception:
        traceback.print_exc()

    print("import faster_whisper", flush=True)
    from faster_whisper import WhisperModel

    print("try cpu int8 load...", flush=True)
    try:
        m = WhisperModel(str(MODEL_DIR), device="cpu", compute_type="int8")
        print("CPU LOADED", flush=True)
        del m
    except Exception:
        traceback.print_exc()
        return 1

    print("try cuda float16 load...", flush=True)
    try:
        m = WhisperModel(str(MODEL_DIR), device="cuda", compute_type="float16")
        print("CUDA LOADED", flush=True)
        del m
    except Exception:
        traceback.print_exc()
        print("CUDA unavailable, CPU works", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
