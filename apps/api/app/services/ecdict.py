"""Offline English→Chinese word lookup backed by an ECDICT SQLite file.

The db comes from the skywind3000/ECDICT release (ecdict-sqlite-28.zip,
table `stardict`). Lookup is a single indexed SELECT — no network involved.
"""

from __future__ import annotations

import re
import sqlite3
import threading
from pathlib import Path

from ..config import settings

_LOCK = threading.Lock()
_CONN: sqlite3.Connection | None = None
_WORD_EXPR = ""  # "sw" when the db ships a pre-lowered search column, else "word"
_UNAVAILABLE = False  # missing/broken db — remember so hover lookups stay instant


def _open() -> sqlite3.Connection | None:
    global _CONN, _WORD_EXPR, _UNAVAILABLE
    if _UNAVAILABLE:
        return None
    with _LOCK:
        if _CONN is None:
            path = Path(settings.ecdict_db_path)
            if not path.exists():
                _UNAVAILABLE = True
                return None
            try:
                conn = sqlite3.connect(
                    f"file:{path}?mode=ro", uri=True, check_same_thread=False
                )
                tables = {
                    r[0]
                    for r in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                if "stardict" not in tables:
                    _UNAVAILABLE = True
                    return None
                cols = {r[1] for r in conn.execute("PRAGMA table_info(stardict)")}
                _WORD_EXPR = "sw" if "sw" in cols else "word"
                _CONN = conn
            except sqlite3.Error:
                _UNAVAILABLE = True
                return None
        return _CONN


def available() -> bool:
    return _open() is not None


def connection() -> sqlite3.Connection | None:
    """Shared read-only connection for other services (word graph etc.)."""
    return _open()


def _clean_zh(text: str) -> str:
    text = re.sub(r"^[nva](rt|dv)?\.\s*", "", text.strip())
    text = re.sub(r"^(名词|动词|形容词|副词)[:：]\s*", "", text)
    return text.strip()


def lookup(word: str) -> dict | None:
    conn = _open()
    if conn is None:
        return None
    w = (word or "").strip().strip(".,!?;:\"'()[]").lower()
    if not w or len(w) > 64:
        return None
    try:
        row = conn.execute(
            f"SELECT phonetic, definition, translation, pos FROM stardict "
            f"WHERE {_WORD_EXPR} = ? LIMIT 1",
            (w,),
        ).fetchone()
    except sqlite3.Error:
        return None
    if not row:
        return None
    phonetic, definition, translation, pos_col = row

    zh_parts: list[str] = []
    pos = ""
    for line in (translation or "").splitlines():
        text = line.strip()
        if not text:
            continue
        m = re.match(r"^([a-z]+)\.\s*(.+)$", text, re.I)
        if m and not pos:
            pos = m.group(1).lower()
        cleaned = _clean_zh(text)
        if cleaned:
            zh_parts.append(cleaned)
        if len(zh_parts) >= 3:
            break
    meaning_zh = "；".join(zh_parts)
    if not meaning_zh:
        return None

    ipa = (phonetic or "").strip()
    if ipa and not ipa.startswith("/"):
        ipa = f"/{ipa}/"
    return {
        "ipa": ipa,
        "pos": pos or (pos_col or "").split(":")[0].strip(),
        "meaning_zh": meaning_zh[:300],
        "meaning_en": (definition or "").strip().splitlines()[0][:300] if definition else "",
        "source": "ecdict",
    }
