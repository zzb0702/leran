from __future__ import annotations

import hashlib
from pathlib import Path

from .base import AsrProvider, AsrSegment, EnrichProvider, TranslateProvider, WordSpan

# Demo transcript for mock ASR — works offline without API keys.
MOCK_LINES = [
    "So a GPU is really just thousands of tiny cores working in parallel.",
    "That means throughput goes up when the workload can be split.",
    "Memory bandwidth often becomes the next bottleneck after that.",
    "If you train a model here, watch the batch size and learning rate.",
    "The cloud option is faster, but your data leaves the machine.",
    "Local whisper is slower on CPU and much better with a GPU.",
    "Let's compare the two providers before we ship the pipeline.",
    "You can re-run a single line if the transcript looks wrong.",
    "Pick a word in the subtitle and it becomes a flashcard.",
    "Review it tomorrow and jump back to this exact second.",
    "Previously on this episode, the team argued about latency.",
    "She said the contract had already been signed last winter.",
    "We never should have left the city without telling anyone.",
    "There is still time to change the ending if we hurry.",
    "Do you really think they will believe that story again?",
    "The train leaves at midnight and we are not on it yet.",
]


def _probe_ms(path: Path) -> int:
    try:
        from ..media_tools import probe_duration_ms

        return probe_duration_ms(path) or 0
    except Exception:  # noqa: BLE001
        return 0


class MockAsrProvider(AsrProvider):
    """Offline demo ASR. For a 45min file it scales lines so the pipeline looks real."""

    provider_id = "mock"

    def transcribe(self, audio_path: str, language: str = "en") -> list[AsrSegment]:
        path = Path(audio_path)
        seed = int(hashlib.md5(path.name.encode()).hexdigest()[:8], 16)
        duration_ms = _probe_ms(path)
        if duration_ms <= 0:
            # ~few lines for tiny clips
            count = 6 + (seed % 5)
        else:
            # ~1 spoken line / 2.6s of dialogue-ish pace; cap to keep mock snappy
            count = max(4, min(400, int(duration_ms / 2600)))

        segments: list[AsrSegment] = []
        t = 0
        avg = max(1800, (duration_ms // count) - 250) if duration_ms > 0 else 2200
        for i in range(count):
            text = MOCK_LINES[i % len(MOCK_LINES)]
            duration = avg if duration_ms > 0 else 2200 + (len(text) % 7) * 120
            words: list[WordSpan] = []
            cursor = t
            tokens = text.split()
            step = max(duration // max(len(tokens), 1), 40)
            for w in tokens:
                words.append(WordSpan(text=w, start_ms=cursor, end_ms=cursor + step))
                cursor += step
            end = min(t + duration, duration_ms) if duration_ms > 0 else t + duration
            if end <= t:
                end = t + duration
            segments.append(AsrSegment(start_ms=t, end_ms=end, text=text, words=words))
            t = end + 200
            if duration_ms and t >= duration_ms:
                break
        return segments


MOCK_ZH = [
    "所以 GPU 其实就是成千上万个并行工作的小核心。",
    "这意味着当工作负载可以拆分时，吞吐量会上升。",
    "在这之后，显存带宽往往会成为下一个瓶颈。",
    "如果你在这里训练模型，要注意 batch size 和学习率。",
    "云端方案更快，但你的数据会离开本机。",
    "本地 Whisper 在 CPU 上更慢，有 GPU 会好很多。",
    "上线流水线之前，我们先对比一下两个 Provider。",
    "如果某一行识别错了，可以单独重跑。",
    "在字幕里点一个词，它就会变成闪卡。",
    "明天复习时，可以直接跳回这一秒。",
    "上集回顾里，团队还在为延迟争吵。",
    "她说合同去年冬天就已经签了。",
    "我们不该谁也不说就离开这座城市。",
    "如果动作快，还来得及改结局。",
    "你真觉得他们会再信那个故事吗？",
    "火车午夜发车，我们还没上车。",
]


class MockTranslateProvider(TranslateProvider):
    provider_id = "mock"

    def translate_batch(
        self,
        texts: list[str],
        *,
        context_before: list[str] | None = None,
        context_after: list[str] | None = None,
        glossary: dict[str, str] | None = None,
    ) -> list[str]:
        out: list[str] = []
        for i, text in enumerate(texts):
            zh = MOCK_ZH[i % len(MOCK_ZH)]
            if glossary:
                for en, keep in glossary.items():
                    if en.lower() in text.lower() and keep:
                        zh = f"{zh}（{keep}）"
                        break
            out.append(zh)
        return out


# Lightweight demo lexicon so hover lookup is useful without an API key.
_MOCK_LEXICON: dict[str, dict[str, str]] = {
    "suite": {"pos": "n", "ipa": "/swiːt/", "meaning_zh": "套房；一套家具；组曲"},
    "throughput": {"pos": "n", "ipa": "/ˈθruːpʊt/", "meaning_zh": "吞吐量，处理能力"},
    "bandwidth": {"pos": "n", "ipa": "/ˈbændwɪdθ/", "meaning_zh": "带宽"},
    "parallel": {"pos": "adj", "ipa": "/ˈpærəlel/", "meaning_zh": "平行的；并行的"},
    "workload": {"pos": "n", "ipa": "/ˈwɜːrkloʊd/", "meaning_zh": "工作负载"},
    "bottleneck": {"pos": "n", "ipa": "/ˈbɑːtlnek/", "meaning_zh": "瓶颈"},
    "latency": {"pos": "n", "ipa": "/ˈleɪtənsi/", "meaning_zh": "延迟"},
    "contract": {"pos": "n", "ipa": "/ˈkɑːntrækt/", "meaning_zh": "合同；收缩"},
    "train": {"pos": "n", "ipa": "/treɪn/", "meaning_zh": "火车；训练"},
    "episode": {"pos": "n", "ipa": "/ˈepɪsoʊd/", "meaning_zh": "一集；插曲"},
    "gpu": {"pos": "n", "ipa": "/ˌdʒiː piː ˈjuː/", "meaning_zh": "图形处理器"},
    "cores": {"pos": "n", "ipa": "/kɔːrz/", "meaning_zh": "核心（core 的复数）"},
    "split": {"pos": "v", "ipa": "/splɪt/", "meaning_zh": "拆分；分开"},
    "cloud": {"pos": "n", "ipa": "/klaʊd/", "meaning_zh": "云；云端"},
    "provider": {"pos": "n", "ipa": "/prəˈvaɪdər/", "meaning_zh": "提供方，供应商"},
    "subtitle": {"pos": "n", "ipa": "/ˈsʌbtaɪtl/", "meaning_zh": "字幕"},
    "flashcard": {"pos": "n", "ipa": "/ˈflæʃkɑːrd/", "meaning_zh": "闪卡，记忆卡片"},
    "eighth": {"pos": "adj", "ipa": "/eɪtθ/", "meaning_zh": "第八"},
    "floor": {"pos": "n", "ipa": "/flɔːr/", "meaning_zh": "楼层；地板"},
    "our": {"pos": "pron", "ipa": "/aʊər/", "meaning_zh": "我们的"},
    "on": {"pos": "prep", "ipa": "/ɑːn/", "meaning_zh": "在…上"},
    "the": {"pos": "art", "ipa": "/ðə/", "meaning_zh": "这；那（定冠词）"},
}


class MockEnrichProvider(EnrichProvider):
    provider_id = "mock"

    def define_in_context(self, headword: str, sentence: str, locale: str = "zh") -> dict:
        key = (headword or "").strip().lower()
        hit = _MOCK_LEXICON.get(key)
        if hit:
            return {
                "headword": key,
                "pos": hit["pos"],
                "ipa": hit["ipa"],
                "meaning_zh": hit["meaning_zh"],
                "example_en": sentence,
                "example_zh": "",
            }
        return {
            "headword": key,
            "pos": "",
            "ipa": "",
            "meaning_zh": f"（语境义）{headword}",
            "example_en": sentence,
            "example_zh": "",
        }

    def compose_story(self, words: list[str]) -> str:
        picks = [w.strip() for w in words if w.strip()][:20] or ["story"]
        bolded = ", ".join(f"**{w}**" for w in picks)
        return (
            f"This is a mock demo story. Imagine a learner collecting {bolded}. "
            "Each new word waits quietly in a notebook, hoping to be reviewed before "
            "it fades away. Configure an LLM provider in Settings to get a real "
            "memory-boosting story.\n"
            "===\n"
            "（mock 演示作文）在「设置 → 释义 Enrich」配置 OpenAI 兼容的 Key 后，"
            "这里会生成一篇真正串联当天新词的英文小短文并附中文翻译。"
        )
