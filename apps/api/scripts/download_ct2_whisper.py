"""Download a CTranslate2 Whisper model usable by faster-whisper (Distil/turbo)."""
from __future__ import annotations

import os
import time
from pathlib import Path

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HOME", r"E:\leran-models\hf")
os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")

from huggingface_hub import snapshot_download

ROOT = Path(r"E:\leran-models\whisper")
ROOT.mkdir(parents=True, exist_ok=True)

# CT2 repos that faster-whisper can actually load.
# Distil-Whisper original is PyTorch — use turbo CT2 (same speed class) first,
# then standard large-v3 CT2.
REPOS = [
    "deepdml/faster-whisper-large-v3-turbo-ct2",
    "Systran/faster-whisper-large-v3",
]


def main() -> int:
    for repo in REPOS:
        print(f"=== snapshot_download {repo} ===", flush=True)
        t0 = time.time()
        try:
            path = snapshot_download(
                repo_id=repo,
                local_dir=str(ROOT / repo.replace("/", "__")),
                resume_download=True,
                max_workers=4,
            )
            print(f"DOWNLOADED {repo} -> {path} in {time.time() - t0:.1f}s", flush=True)
            # list weights
            for p in Path(path).rglob("*"):
                if p.is_file() and p.suffix in {".bin", ".pt", ".onnx", ".ct2"} or p.name in {
                    "model.bin",
                    "config.json",
                    "tokenizer.json",
                    "vocabulary.txt",
                }:
                    print(f"  {p.relative_to(path)} {p.stat().st_size/1024/1024:.1f}MB", flush=True)
            return 0
        except Exception as e:  # noqa: BLE001
            print(f"FAIL {repo}: {type(e).__name__}: {e}", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
