from __future__ import annotations

from pathlib import Path

from .base import AsrProvider, AsrSegment, WordSpan

_MODEL_CACHE: dict[tuple, object] = {}
_CUDA_DLL_READY = False


def ensure_cuda_dlls() -> bool:
    """Put nvidia cuDNN (and friends) on the Windows DLL search path for CT2."""
    global _CUDA_DLL_READY
    if _CUDA_DLL_READY:
        return True
    import os
    import sys

    candidates: list[Path] = []
    sp = Path(sys.prefix) / "Lib" / "site-packages" / "nvidia"
    for sub in ("cudnn/bin", "cudnn/lib", "cublas/bin", "cuda_runtime/bin", "cuda_runtime/lib"):
        p = sp / sub.replace("/", os.sep)
        if p.is_dir():
            candidates.append(p)
    # Also allow explicit override
    extra = os.environ.get("LERAN_CUDA_DLL_DIR")
    if extra and Path(extra).is_dir():
        candidates.append(Path(extra))

    for p in candidates:
        try:
            os.add_dll_directory(str(p))
        except (OSError, ValueError):
            pass
        # PATH helps some native deps that don't use the modern loader
        os.environ["PATH"] = str(p) + os.pathsep + os.environ.get("PATH", "")

    _CUDA_DLL_READY = True
    return True


def _cuda_available() -> bool:
    try:
        import ctranslate2

        return ctranslate2.get_cuda_device_count() > 0
    except Exception:  # noqa: BLE001
        return False


def _resolve_model_ref(model: str) -> str:
    """Map friendly names / local CT2 dirs to a faster-whisper load target."""
    from ...config import settings

    model = (model or "").strip()
    if not model:
        model = settings.local_whisper_model or "base"

    # Absolute or relative local CT2 directory
    p = Path(model)
    if p.is_dir():
        return str(p)

    # Known local snapshot on this machine (Distil-class turbo CT2)
    turbo = Path(settings.local_whisper_download_root) / "deepdml__faster-whisper-large-v3-turbo-ct2"
    if turbo.is_dir() and model.lower() in {
        "distil",
        "distil-large-v3",
        "turbo",
        "large-v3-turbo",
        "distil-turbo",
    }:
        return str(turbo)

    # Passthrough HF repo id (Systran/faster-whisper-base, distil-whisper/..., etc.)
    return model


class LocalWhisperProvider(AsrProvider):
    """faster-whisper local ASR. Prefer ctranslate2==4.4.0 on this Windows box."""

    provider_id = "local-whisper"

    def __init__(
        self,
        model_size: str = "",
        device: str = "",
        compute_type: str = "",
    ) -> None:
        from ...config import settings

        self.model_ref = _resolve_model_ref(model_size)
        self.device = (device or settings.local_whisper_device or "auto").strip()
        self.compute_type = (compute_type or "").strip()
        self.cpu_threads = settings.local_whisper_cpu_threads
        self.use_vad = settings.local_whisper_vad
        self.download_root = settings.local_whisper_download_root

    def _pick_device_compute(self) -> tuple[str, str]:
        if self.device not in {"auto", "cuda", "cpu"}:
            device = "auto"
        else:
            device = self.device
        compute = self.compute_type
        if device == "auto":
            ensure_cuda_dlls()
            if _cuda_available():
                device = "cuda"
                compute = compute or "float16"
            else:
                device = "cpu"
                compute = compute or "int8"
            return device, compute
        if device == "cuda":
            ensure_cuda_dlls()
            compute = compute or "float16"
        if device == "cpu":
            compute = compute or "int8"
        return device, compute

    def _load_model(self):
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper 未安装。请在 apps/api 执行: pip install faster-whisper ctranslate2==4.4.0"
            ) from exc

        device, compute = self._pick_device_compute()
        key = (self.model_ref, device, compute, self.cpu_threads)
        if key in _MODEL_CACHE:
            return _MODEL_CACHE[key]

        kwargs: dict = {
            "device": device,
            "compute_type": compute,
        }
        if device == "cpu":
            kwargs["cpu_threads"] = self.cpu_threads
        # Only pass download_root when target is a HF id, not a local dir.
        if not Path(self.model_ref).is_dir() and self.download_root:
            kwargs["download_root"] = str(self.download_root)

        model = WhisperModel(self.model_ref, **kwargs)
        _MODEL_CACHE[key] = model
        return model

    def transcribe(self, audio_path: str, language: str = "en") -> list[AsrSegment]:
        from ...config import settings

        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(audio_path)

        audio_file = path
        if path.suffix.lower() in {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v"}:
            audio_file = self._extract_audio(path)
            if audio_file is None:
                raise RuntimeError("ffmpeg 不可用，无法从视频抽取音频用于本地 ASR")

        model = self._load_model()
        segments_iter, _info = model.transcribe(
            str(audio_file),
            language=language,
            word_timestamps=True,
            # VAD can hang with some webrtcvader builds — off by default.
            vad_filter=self.use_vad,
            beam_size=1,
        )
        out: list[AsrSegment] = []
        for seg in segments_iter:
            words: list[WordSpan] = []
            for w in seg.words or []:
                words.append(
                    WordSpan(
                        text=(w.word or "").strip(),
                        start_ms=int(w.start * 1000),
                        end_ms=int(w.end * 1000),
                    )
                )
            text = (seg.text or "").strip()
            if not text:
                continue
            out.append(
                AsrSegment(
                    start_ms=int(seg.start * 1000),
                    end_ms=int(seg.end * 1000),
                    text=text,
                    words=words,
                )
            )
        return out

    def _extract_audio(self, video_path: Path) -> Path | None:
        import shutil
        import subprocess

        from ...config import settings

        ffmpeg = settings.ffmpeg_path or shutil.which("ffmpeg")
        if not ffmpeg or not Path(ffmpeg).exists():
            return None
        out = video_path.with_suffix(".16k.wav")
        if out.exists():
            return out
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(out),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=600)
            if proc.returncode == 0 and out.exists():
                return out
        except (OSError, subprocess.TimeoutExpired):
            return None
        return None
