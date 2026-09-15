from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class WordSpan:
    text: str
    start_ms: int
    end_ms: int


@dataclass
class AsrSegment:
    start_ms: int
    end_ms: int
    text: str
    words: list[WordSpan] = field(default_factory=list)


class AsrProvider:
    provider_id = "base"

    def transcribe(self, audio_path: str, language: str = "en") -> list[AsrSegment]:
        raise NotImplementedError


class TranslateProvider:
    provider_id = "base"

    def translate_batch(
        self,
        texts: list[str],
        *,
        context_before: list[str] | None = None,
        context_after: list[str] | None = None,
        glossary: dict[str, str] | None = None,
    ) -> list[str]:
        raise NotImplementedError


class EnrichProvider:
    provider_id = "base"

    def define_in_context(self, headword: str, sentence: str, locale: str = "zh") -> dict:
        raise NotImplementedError

    def compose_story(self, words: list[str]) -> str:
        raise NotImplementedError
