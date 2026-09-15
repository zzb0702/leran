from __future__ import annotations

import json
from pathlib import Path

import httpx

from ...config import settings
from .base import AsrProvider, AsrSegment, EnrichProvider, TranslateProvider, WordSpan


class OpenAiAsrProvider(AsrProvider):
    provider_id = "openai"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = api_key or settings.openai_api_key
        self.base_url = (base_url or settings.openai_base_url).rstrip("/")
        self.model = model or settings.openai_asr_model

    def transcribe(self, audio_path: str, language: str = "en") -> list[AsrSegment]:
        if not self.api_key:
            raise RuntimeError("OpenAI API key not configured")

        path = Path(audio_path)
        # Cloud Whisper limit is 25MB — split if pipeline didn't already.
        max_bytes = settings.openai_max_file_mb * 1024 * 1024
        if path.exists() and path.stat().st_size > max_bytes:
            return self._transcribe_long_file(path, language)

        return self._transcribe_one(path, language)

    def _transcribe_one(self, path: Path, language: str, offset_ms: int = 0) -> list[AsrSegment]:
        with open(path, "rb") as f:
            files = {"file": (path.name, f, "application/octet-stream")}
            data = {
                "model": self.model,
                "language": language,
                "response_format": "verbose_json",
                "timestamp_granularities[]": "word",
            }
            resp = httpx.post(
                f"{self.base_url}/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                files=files,
                data=data,
                timeout=settings.asr_timeout_s,
            )
        resp.raise_for_status()
        payload = resp.json()
        segments: list[AsrSegment] = []
        for seg in payload.get("segments") or []:
            start = int(float(seg.get("start", 0)) * 1000) + offset_ms
            end = int(float(seg.get("end", 0)) * 1000) + offset_ms
            text = (seg.get("text") or "").strip()
            words: list[WordSpan] = []
            for w in seg.get("words") or []:
                words.append(
                    WordSpan(
                        text=str(w.get("word") or w.get("text") or "").strip(),
                        start_ms=int(float(w.get("start", 0)) * 1000) + offset_ms,
                        end_ms=int(float(w.get("end", 0)) * 1000) + offset_ms,
                    )
                )
            if text:
                segments.append(AsrSegment(start_ms=start, end_ms=end, text=text, words=words))
        if not segments and payload.get("text"):
            segments.append(AsrSegment(offset_ms, offset_ms, str(payload["text"]).strip(), []))
        return segments

    def _transcribe_long_file(self, path: Path, language: str) -> list[AsrSegment]:
        """Fallback split by time if file still exceeds cloud size limit."""
        from ..media_tools import probe_duration_ms, split_audio_chunks

        duration = probe_duration_ms(path) or 0
        if duration <= 0:
            raise RuntimeError("Cannot split oversized ASR file (unknown duration)")
        slices = split_audio_chunks(
            path,
            duration,
            chunk_minutes=min(10.0, settings.asr_chunk_minutes),
            work_dir=path.parent / f"{path.name}_openai_slices",
        )
        all_segs: list[AsrSegment] = []
        try:
            for sl in slices:
                all_segs.extend(self._transcribe_one(sl.path, language, offset_ms=sl.start_ms))
        finally:
            for sl in slices:
                if sl.path != path:
                    sl.path.unlink(missing_ok=True)
            work = path.parent / f"{path.name}_openai_slices"
            if work.exists():
                try:
                    work.rmdir()
                except OSError:
                    pass
        return all_segs


class OpenAiTranslateProvider(TranslateProvider):
    provider_id = "openai"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = api_key or settings.openai_api_key
        self.base_url = (base_url or settings.openai_base_url).rstrip("/")
        self.model = model or settings.openai_chat_model

    def translate_batch(
        self,
        texts: list[str],
        *,
        context_before: list[str] | None = None,
        context_after: list[str] | None = None,
        glossary: dict[str, str] | None = None,
    ) -> list[str]:
        if not self.api_key:
            raise RuntimeError("OpenAI API key not configured")
        if not texts:
            return []

        before = "\n".join(context_before or [])
        after = "\n".join(context_after or [])
        gloss_lines = "\n".join(f"- {k} => {v}" for k, v in (glossary or {}).items())
        numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(texts))
        system = (
            "You are a professional subtitle translator. Translate English subtitles to Simplified Chinese. "
            "Return ONLY a JSON array of strings, same length and order as input lines. "
            "Keep proper nouns per glossary. Natural spoken Chinese, concise, no explanations."
        )
        user = (
            f"Context before:\n{before}\n\nLines to translate:\n{numbered}\n\n"
            f"Context after:\n{after}\n\nGlossary:\n{gloss_lines or '(none)'}"
        )
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=settings.translate_timeout_s,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        parsed = _parse_json_array(content)
        if len(parsed) != len(texts):
            # Fallback: pad/truncate to keep alignment stable.
            parsed = (parsed + texts)[: len(texts)]
            if len(parsed) < len(texts):
                parsed = parsed + [""] * (len(texts) - len(parsed))
        return [str(x) for x in parsed]


def _parse_json_array(content: str) -> list[str]:
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.startswith("json"):
            content = content[4:].strip()
    start = content.find("[")
    end = content.rfind("]")
    if start >= 0 and end > start:
        content = content[start : end + 1]
    data = json.loads(content)
    if isinstance(data, list):
        return [str(x) for x in data]
    raise ValueError("Model did not return a JSON array")


class OpenAiEnrichProvider(EnrichProvider):
    provider_id = "openai"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = api_key or settings.openai_api_key
        self.base_url = (base_url or settings.openai_base_url).rstrip("/")
        self.model = model or settings.openai_chat_model

    def define_in_context(self, headword: str, sentence: str, locale: str = "zh") -> dict:
        if not self.api_key:
            raise RuntimeError("OpenAI API key not configured")
        prompt = (
            "Define the English word as used in this sentence for a Chinese learner. "
            'Return JSON: {"headword","pos","ipa","meaning_zh","example_en","example_zh"}.\n'
            f"Word: {headword}\nSentence: {sentence}"
        )
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "temperature": 0.2,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        start = content.find("{")
        end = content.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Invalid enrich response")
        data = json.loads(content[start : end + 1])
        data.setdefault("headword", headword)
        data.setdefault("example_en", sentence)
        return data

    def compose_story(self, words: list[str]) -> str:
        if not self.api_key:
            raise RuntimeError("OpenAI API key not configured")
        clean = [w.strip() for w in words if w.strip()][:20]
        if not clean:
            raise ValueError("No words to compose a story from")
        system = (
            "You are an English writing tutor helping a Chinese learner memorize "
            "vocabulary through context."
        )
        user = (
            "Write ONE short coherent English story (90-140 words, vivid, natural, "
            f"roughly CEFR B1-B2) that uses ALL of these words: {', '.join(clean)}.\n"
            "Rules:\n"
            "- Mark every target word with markdown bold (**word**), including inflected forms.\n"
            "- The story must make sense as a whole, not separate example sentences.\n"
            "- After the story, output a line containing only === and then a fluent "
            "Simplified Chinese translation of the story.\n"
            "- Output nothing else: no title, no notes, no explanations."
        )
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "temperature": 0.7,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=120,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        if not content:
            raise ValueError("Empty story response")
        return content
