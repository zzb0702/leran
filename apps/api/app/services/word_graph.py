"""Word knowledge graph — all offline, on top of the ECDICT sqlite db.

For one headword we derive four families:
- inflections: ECDICT `exchange` column (past/past-participle/-ing/3rd-person/er/est)
- family: derivational suffix relatives that exist as real words (courage → courageous)
- roots: built-in Latin/Greek root table match; siblings = frequent words sharing the root
- similar: real words within edit distance ≤ 2 that mean something else (adapt/adopt)

Everything is frequency-ranked (ECDICT frq/bnc) so the graph stays small and useful.
"""

from __future__ import annotations

import re
import threading

from . import ecdict

_LOCK = threading.Lock()
_VOCAB: dict[str, tuple[str, int]] | None = None  # word -> (short zh, effective rank)
_CACHE: dict[str, dict] = {}

# (root, 中文含义). Curated common Latin/Greek roots/prefixes worth learning.
_ROOTS: list[tuple[str, str]] = [
    ("spect", "看"), ("vis", "看"), ("vid", "看"), ("view", "看"), ("aud", "听"),
    ("phon", "声音"), ("log", "言语/学科"), ("loqu", "说话"), ("dict", "说"),
    ("scrib", "写"), ("script", "写"), ("graph", "写/画"), ("lect", "读/选/讲"),
    ("leg", "读/法"), ("cap", "抓/拿/头"), ("cept", "拿"), ("ceive", "拿"),
    ("mit", "送"), ("miss", "送"), ("port", "搬运"), ("fer", "带来"),
    ("duct", "引导"), ("duc", "引导"), ("tract", "拉/拖"),
    ("press", "压"), ("pel", "推"), ("puls", "推"), ("ject", "扔"),
    ("pos", "放置"), ("pon", "放置"), ("tain", "握/持"),
    ("ten", "握/持"), ("hab", "持有/居住"), ("rupt", "破裂"), ("struct", "建造"),
    ("form", "形状"), ("fig", "形状"), ("morph", "形状"), ("gen", "出生/产生"),
    ("nat", "出生"), ("bio", "生命"), ("vit", "生命"), ("viv", "活"),
    ("mort", "死"), ("anim", "生命/精神"), ("cord", "心"), ("card", "心"),
    ("cor", "心"), ("psych", "心理"), ("mem", "记忆"), ("mind", "心智"),
    ("man", "手"), ("ped", "脚"), ("pod", "脚"), ("dent", "牙齿"),
    ("ocul", "眼睛"), ("optic", "眼睛"), ("aur", "耳"), ("nas", "鼻"),
    ("cid", "落/切"), ("cis", "切"), ("sect", "切"), ("tom", "切"),
    ("circ", "圆/环"), ("cycl", "圆/环"), ("angl", "角"), ("rect", "直/正"),
    ("und", "波/流"), ("cur", "跑/流"), ("curs", "跑"), ("fluent", "流"),
    ("flu", "流"), ("grad", "步/级"), ("gress", "行走"), ("vent", "来"),
    ("ven", "来"), ("it", "行走"), ("migr", "迁移"), ("mot", "移动"),
    ("mov", "移动"), ("stat", "站"), ("sist", "站立"), ("st", "站立"),
    ("spond", "承诺/回答"), ("valu", "价值"), ("worth", "价值"),
    ("prec", "价值/祈祷"), ("dur", "持久"), ("tempor", "时间"), ("chron", "时间"),
    ("ann", "年"), ("enn", "年"), ("di", "日"), ("noct", "夜"), ("lumin", "光"),
    ("luc", "光"), ("clar", "清楚/明亮"), ("therm", "热"), ("frig", "冷"),
    ("fort", "强"), ("val", "强/价值"), ("viol", "暴力"), ("pot", "能力/力量"),
    ("dyn", "力量"), ("electr", "电"), ("magn", "大/磁"), ("grand", "大"),
    ("maj", "大"), ("min", "小"), ("micro", "小"), ("multi", "多"),
    ("poly", "多"), ("homo", "同"), ("hetero", "异"), ("sym", "共同"),
    ("syn", "共同"), ("auto", "自动/自己"), ("tele", "远"), ("trans", "跨越/转移"),
    ("sub", "下/次"), ("super", "超/上"), ("inter", "之间"), ("intro", "向内"),
    ("extra", "额外"), ("ultra", "超出"), ("anti", "反对"), ("counter", "反对"),
    ("pre", "前"), ("post", "后"), ("fore", "前"), ("re", "再次/返回"),
    ("ex", "向外/前任"), ("im", "向内/否定"), ("in", "向内/否定"), ("ob", "逆/对抗"),
    ("de", "去除/向下"), ("dis", "分散/否定"), ("mis", "错误"), ("over", "过度"),
    ("under", "不足"), ("semi", "半"), ("uni", "单"), ("mono", "单"),
    ("bi", "双"), ("tri", "三"), ("quadr", "四"), ("penta", "五"),
    ("dec", "十"), ("cent", "百"), ("mill", "千"), ("sect", "派别/切"),
]
_ROOTS = [(r.strip(), m) for r, m in _ROOTS if len(r.strip()) >= 2]
# 去重（同根多写法保留首个）
_seen: set[str] = set()
_ROOTS = [(r, m) for r, m in _ROOTS if not (r in _seen or _seen.add(r))]

# exchange code → label
_INFLECT_LABELS = {
    "p": "过去式",
    "d": "过去分词",
    "i": "现在分词",
    "3": "三单",
    "r": "比较级",
    "t": "最高级",
    "s": "原形",
    "0": "原形",
}

# derivational suffixes, longest first
_SUFFIXES = [
    "ation", "ition", "ution", "sion", "tion", "ment", "ness", "ship",
    "hood", "ance", "ence", "ancy", "ency", "able", "ible", "ally",
    "ify", "ize", "ise", "ful", "less", "ous", "ive", "ant", "ent",
    "er", "or", "ist", "ism", "ly", "ing", "ed", "al", "ic", "en", "y",
]


def _short_zh(translation: str | None) -> str:
    line = (translation or "").strip().splitlines()
    if not line or not line[0]:
        return ""
    text = re.sub(r"^[nva](rt|dv)?\.\s*", "", line[0])
    return text[:40]


def _load_vocab() -> dict[str, tuple[str, int]]:
    global _VOCAB
    if _VOCAB is not None:
        return _VOCAB
    with _LOCK:
        if _VOCAB is not None:
            return _VOCAB
        conn = ecdict.connection()
        vocab: dict[str, tuple[str, int]] = {}
        if conn is not None:
            try:
                rows = conn.execute(
                    "SELECT word, translation, frq, bnc FROM stardict "
                    "WHERE (frq > 0 AND frq <= 80000) OR (bnc > 0 AND bnc <= 80000)"
                ).fetchall()
                for word, translation, frq, bnc in rows:
                    w = (word or "").strip().lower()
                    if not w or " " in w or not w.isascii():
                        continue
                    ranks = [r for r in (frq, bnc) if r and r > 0]
                    rank = min(ranks) if ranks else 99999
                    vocab[w] = (_short_zh(translation), rank)
            except Exception:  # noqa: BLE001
                vocab = {}
        _VOCAB = vocab
    return _VOCAB


def _edit_distance(a: str, b: str, cap: int = 2) -> int:
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > cap:
            return cap + 1
        prev = cur
    return prev[-1]


def _parse_exchange(raw: str | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in (raw or "").split("/"):
        if ":" in part:
            code, form = part.split(":", 1)
            code, form = code.strip(), form.strip()
            if code in _INFLECT_LABELS and form and form != "-":
                out[code] = form
    return out


def _family(word: str, vocab: dict[str, tuple[str, int]]) -> list[dict]:
    """Derivational relatives: strip a suffix to a real base, then regrow other suffixes."""
    base = ""
    for suf in _SUFFIXES:
        if word.endswith(suf) and len(word) - len(suf) >= 3:
            stem = word[: -len(suf)]
            for cand in (stem, stem + "e"):
                if cand in vocab:
                    base = cand
                    break
            if base:
                break
    if not base:
        base = word
    out: dict[str, dict] = {}
    if base != word:
        out[base] = {"word": base, "label": "原词", "zh": vocab[base][0]}
    for suf in _SUFFIXES:
        cand = base + suf
        if cand == word or cand in out or cand not in vocab:
            continue
        if cand.endswith("e") and cand[:-1] in vocab:  # e.g. Courage + ous
            continue
        out[cand] = {"word": cand, "label": f"-{suf}", "zh": vocab[cand][0]}
    ranked = sorted(out.values(), key=lambda n: vocab.get(n["word"], ("", 9e9))[1])
    return ranked[:10]


def _similar(word: str, vocab: dict[str, tuple[str, int]]) -> list[dict]:
    """Same first letter, length ±1, edit distance ≤ 2 — frequent words only."""
    cands: list[tuple[int, str]] = []
    n = len(word)
    for cand, (_zh, rank) in vocab.items():
        if rank > 30000 or abs(len(cand) - n) > 1 or cand[0] != word[0]:
            continue
        if cand == word:
            continue
        d = _edit_distance(word, cand)
        if d <= 2:
            cands.append((rank + (d - 1) * 8000, cand))
    cands.sort()
    return [
        {"word": c, "label": f"差{ _edit_distance(word, c)}字符", "zh": vocab[c][0]}
        for _r, c in cands[:10]
    ]


def _roots(word: str, vocab: dict[str, tuple[str, int]]) -> list[dict]:
    hits: list[dict] = []
    for root, meaning in _ROOTS:
        if root in word and len(root) >= 3:
            siblings: list[tuple[int, str]] = []
            for cand, (_zh, rank) in vocab.items():
                if rank > 25000 or cand == word or len(cand) < 4:
                    continue
                if root in cand:
                    siblings.append((rank, cand))
            siblings.sort()
            hits.append(
                {
                    "root": root,
                    "meaning": meaning,
                    "words": [
                        {"word": w, "label": "", "zh": vocab[w][0]}
                        for _r, w in siblings[:8]
                    ],
                }
            )
    hits.sort(key=lambda h: -len(h["words"]))
    return hits[:3]


def build_graph(word: str) -> dict | None:
    w = (word or "").strip().strip(".,!?;:\"'()[]").lower()
    if not w or len(w) > 40:
        return None
    with _LOCK:
        if w in _CACHE:
            return _CACHE[w]

    center = ecdict.lookup(w)
    vocab = _load_vocab()
    if not center and w not in vocab:
        return None

    exchange = {}
    conn = ecdict.connection()
    if conn is not None:
        try:
            row = conn.execute(
                "SELECT exchange FROM stardict WHERE sw = ? LIMIT 1", (w,)
            ).fetchone()
            exchange = _parse_exchange(row[0] if row else None)
        except Exception:  # noqa: BLE001
            exchange = {}

    inflections: list[dict] = []
    seen_forms: set[str] = set()
    for code, form in exchange.items():
        if code == "1" or form in seen_forms or form == w:
            continue
        seen_forms.add(form)
        inflections.append(
            {"word": form, "label": _INFLECT_LABELS[code], "zh": vocab.get(form, ("", 9))[0]}
        )
        if len(inflections) >= 6:
            break

    zh = center.get("meaning_zh", "") if center else vocab.get(w, ("", 0))[0]
    graph = {
        "word": w,
        "ipa": (center or {}).get("ipa", ""),
        "pos": (center or {}).get("pos", ""),
        "meaning_zh": zh,
        "groups": {
            "inflections": inflections,
            "family": _family(w, vocab),
            "similar": _similar(w, vocab),
            "roots": _roots(w, vocab),
        },
    }
    with _LOCK:
        _CACHE[w] = graph
        if len(_CACHE) > 2000:
            for k in list(_CACHE.keys())[:1000]:
                _CACHE.pop(k, None)
    return graph
