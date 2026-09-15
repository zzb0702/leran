from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from pathlib import Path

import httpx

from ..config import settings

_CACHE: dict[str, dict] = {}
_LOCK = threading.Lock()
_CACHE_PATH = Path(settings.media_dir).parent / "dict_cache.json"

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LeranDict/0.1"


def _load_disk_cache() -> None:
    global _CACHE
    try:
        if _CACHE_PATH.exists():
            data = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                _CACHE = data
    except (OSError, json.JSONDecodeError):
        _CACHE = {}


def _save_disk_cache() -> None:
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        if len(_CACHE) > 8000:
            items = sorted(_CACHE.items(), key=lambda kv: kv[1].get("_ts", 0), reverse=True)
            _CACHE.clear()
            _CACHE.update(dict(items[:4000]))
        _CACHE_PATH.write_text(json.dumps(_CACHE, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


_load_disk_cache()


def get_cached(word: str) -> dict | None:
    with _LOCK:
        hit = _CACHE.get(word)
    if not hit:
        return None
    return {k: v for k, v in hit.items() if not k.startswith("_")}


def put_cached(word: str, payload: dict) -> None:
    with _LOCK:
        _CACHE[word] = {**payload, "_ts": time.time()}
    _save_disk_cache()


def _clean_zh(text: str) -> str:
    text = re.sub(r"^[nva]\.\s*", "", text.strip())
    text = re.sub(r"^(名词|动词|形容词|副词)[:：]\s*", "", text)
    return text.strip()


def fetch_youdao(word: str) -> dict | None:
    """Fast CN-friendly dictionary (~300ms)."""
    url = "https://dict.youdao.com/jsonapi"
    try:
        r = httpx.get(
            url,
            params={"q": word},
            timeout=3.5,
            headers={"User-Agent": _UA},
        )
        if r.status_code != 200:
            return None
        data = r.json()
        ec = data.get("ec") or {}
        words = ec.get("word") or []
        if not words:
            return None
        w = words[0]
        ipa = w.get("usphone") or w.get("ukphone") or w.get("phone") or ""
        ipa = f"/{ipa}/" if ipa and not ipa.startswith("/") else ipa
        zh_parts: list[str] = []
        pos = ""
        for tr_wrap in w.get("trs") or []:
            try:
                text = tr_wrap["tr"][0]["l"]["i"][0]
            except (KeyError, IndexError, TypeError):
                continue
            if not isinstance(text, str):
                continue
            m = re.match(r"^([a-z]+)\.\s*(.+)$", text.strip(), re.I)
            if m and not pos:
                pos = m.group(1)
            cleaned = _clean_zh(text)
            if cleaned:
                zh_parts.append(cleaned)
            if len(zh_parts) >= 3:
                break
        meaning_zh = "；".join(zh_parts)
        if not meaning_zh:
            # fallback web translation
            try:
                web = data["web_trans"]["web-translation"][0]["trans"]
                meaning_zh = web[0]["value"] if web else ""
            except (KeyError, IndexError, TypeError):
                meaning_zh = ""
        if not meaning_zh and not ipa:
            return None
        return {
            "ipa": ipa,
            "pos": pos,
            "meaning_zh": meaning_zh[:300],
            "meaning_en": "",
            "example_en": "",
            "source": "youdao",
        }
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return None


def fetch_baidu(word: str, appid: str, secret: str) -> dict | None:
    """Baidu Translate general API (official, free tier: 5w chars/month, QPS=1).

    Single-word queries usually come back with POS-prefixed senses, e.g.
    "n. 苹果；苹果树". No IPA. Used as the online fallback after Youdao.
    """
    if not appid or not secret:
        return None
    url = "https://fanyi-api.baidu.com/api/trans/vip/translate"
    salt = str(int(time.time() * 1000))
    sign = hashlib.md5(f"{appid}{word}{salt}{secret}".encode("utf-8")).hexdigest()
    try:
        r = httpx.get(
            url,
            params={
                "q": word,
                "from": "auto",
                "to": "zh",
                "appid": appid,
                "salt": salt,
                "sign": sign,
            },
            timeout=3.0,
            headers={"User-Agent": _UA},
        )
        if r.status_code != 200:
            return None
        data = r.json()
        if "error_code" in data:
            return None
        items = data.get("trans_result") or []
        dst = "；".join(
            str(i.get("dst", "")).strip() for i in items if i.get("dst")
        ).strip()
        if not dst:
            return None
        pos = ""
        m = re.match(r"^([a-z]+)\.\s*", dst, re.I)
        if m:
            pos = m.group(1).lower()
        return {
            "ipa": "",
            "pos": pos,
            "meaning_zh": dst[:300],
            "meaning_en": "",
            "example_en": "",
            "source": "baidu",
        }
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return None


def fetch_free_dictionary(word: str) -> dict | None:
    """English-only fallback (may be slow/blocked in some networks)."""
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
    try:
        r = httpx.get(url, timeout=2.5, follow_redirects=True, headers={"User-Agent": _UA})
        if r.status_code != 200:
            return None
        data = r.json()
        if not isinstance(data, list) or not data:
            return None
        entry = data[0]
        phonetic = ""
        for p in entry.get("phonetics") or []:
            if p.get("text"):
                phonetic = p["text"]
                break
        meanings = entry.get("meanings") or []
        pos = definition = example = ""
        for m in meanings:
            defs = m.get("definitions") or []
            if defs:
                pos = m.get("partOfSpeech") or ""
                definition = defs[0].get("definition") or ""
                example = defs[0].get("example") or ""
                break
        if not definition:
            return None
        return {
            "ipa": phonetic,
            "pos": pos,
            "meaning_zh": "",
            "meaning_en": definition,
            "example_en": example,
            "source": "dictionaryapi",
        }
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return None
