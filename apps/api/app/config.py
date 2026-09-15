from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data"
MEDIA_DIR = DATA_DIR / "media"
CLIP_DIR = DATA_DIR / "clips"
UPLOAD_TMP_DIR = DATA_DIR / "uploads_tmp"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Leran"
    secret_key: str = "dev-secret-change-me"
    access_token_expire_minutes: int = 60 * 24 * 7
    database_url: str = f"sqlite:///{DATA_DIR / 'leran.db'}"
    media_dir: Path = MEDIA_DIR
    clip_dir: Path = CLIP_DIR
    upload_tmp_dir: Path = UPLOAD_TMP_DIR

    # Large-file upload
    max_upload_mb: int = 2048  # 2GB local default; override via .env
    chunk_size_mb: int = 8  # frontend chunk size hint

    # Audio extraction for ASR (large video friendly)
    extract_audio_for_asr: bool = True
    delete_original_after_extract: bool = False  # keep video for playback by default
    audio_extract_timeout_s: int = 1800  # 45min episode extract headroom

    # Long-episode pipeline (~45 min)
    asr_chunk_minutes: float = 10.0  # slice audio before cloud ASR (25MB API limit / stability)
    asr_chunk_overlap_ms: int = 800
    asr_timeout_s: int = 900  # per chunk
    translate_batch_size: int = 8  # smaller batches — avoid provider rate limit
    translate_context_lines: int = 2
    translate_timeout_s: int = 90
    translate_delay_s: float = 1.2  # pause between batches
    translate_max_retries: int = 5
    openai_max_file_mb: int = 24  # under Whisper 25MB hard limit
    max_concurrent_jobs: int = 1  # one media pipeline at a time

    ffmpeg_path: str = ""  # empty = shutil.which("ffmpeg")
    ffprobe_path: str = ""

    # Offline ECDICT lookup (data/ecdict.db built from skywind3000/ECDICT sqlite release)
    ecdict_db_path: str = str(DATA_DIR / "ecdict.db")

    # Local faster-whisper (Distil-class turbo CT2 verified on this machine)
    local_whisper_model: str = "distil"  # or path / HF repo id
    local_whisper_device: str = "auto"  # auto prefers cuda when CT2 sees a GPU
    local_whisper_cpu_threads: int = 8
    local_whisper_vad: bool = False  # VAD hung here; keep off unless proven
    local_whisper_download_root: str = r"E:\leran-models\whisper"

    # Provider defaults: mock | openai | local-whisper
    asr_provider: str = "mock"
    translate_provider: str = "mock"
    enrich_provider: str = "mock"

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_asr_model: str = "whisper-1"
    openai_chat_model: str = "gpt-4o-mini"


settings = Settings()
DATA_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
CLIP_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_TMP_DIR.mkdir(parents=True, exist_ok=True)
