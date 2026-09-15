import sys
import time
import traceback
from pathlib import Path

log = Path(r"E:\leran-models\load_cpu.log")
log.write_text("start\n", encoding="utf-8")


def w(msg: str) -> None:
    with log.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg, flush=True)


try:
    w("importing faster_whisper")
    from faster_whisper import WhisperModel

    p = r"E:\leran-models\whisper\deepdml__faster-whisper-large-v3-turbo-ct2"
    w(f"loading {p}")
    t = time.time()
    m = WhisperModel(p, device="cpu", compute_type="int8")
    w(f"loaded {time.time()-t:.1f}s")

    audio = r"data\speech-sample.wav"
    t = time.time()
    segs, info = m.transcribe(audio, language="en", beam_size=1, word_timestamps=True)
    n = 0
    for s in segs:
        w(f"{s.start:.2f}-{s.end:.2f} {s.text.strip()}")
        n += 1
    w(f"segments={n} elapsed={time.time()-t:.2f} duration={info.duration:.2f}")
    w("done")
except Exception:
    w(traceback.format_exc())
    sys.exit(1)
sys.exit(0)
