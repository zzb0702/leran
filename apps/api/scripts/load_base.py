import os
import sys
import time

os.environ["OMP_NUM_THREADS"] = "4"
os.environ["CT2_USE_MKL"] = "0"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

print("versions", flush=True)
import ctranslate2
import faster_whisper

print("ct2", ctranslate2.__version__, "fw", faster_whisper.__version__, flush=True)

from faster_whisper import WhisperModel

p = r"E:\leran-models\whisper\Systran__faster-whisper-base"
print("load base inter=1...", flush=True)
t = time.time()
try:
    m = WhisperModel(
        p,
        device="cpu",
        compute_type="int8",
        cpu_threads=4,
        num_workers=1,
    )
    print("loaded", time.time() - t, flush=True)
except Exception as e:
    print("ERR", type(e), e, flush=True)
    sys.exit(1)

segs, info = m.transcribe(
    r"data\speech-sample.wav",
    language="en",
    beam_size=1,
)
for s in segs:
    print(s.text.strip(), flush=True)
print("ok duration", info.duration, flush=True)
