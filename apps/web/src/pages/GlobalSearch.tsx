import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, Card, MediaItem } from "../api";

/** Top-bar global search: media titles + vocabulary. Ctrl/Cmd+K to focus. */
export default function GlobalSearch() {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [words, setWords] = useState<Card[]>([]);
  const [sentences, setSentences] = useState<Card[]>([]);
  const [media, setMedia] = useState<MediaItem[]>([]);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const boxRef = useRef<HTMLDivElement | null>(null);
  const nav = useNavigate();

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const t = e.target as HTMLElement | null;
      const typing = t instanceof HTMLInputElement || t instanceof HTMLTextAreaElement;
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        inputRef.current?.focus();
        setOpen(true);
      } else if (e.key === "Escape" && document.activeElement === inputRef.current) {
        setOpen(false);
        inputRef.current?.blur();
      } else if (e.key === "Enter" && document.activeElement === inputRef.current) {
        const first = boxRef.current?.querySelector("a.gs-row") as HTMLAnchorElement | null;
        if (first) {
          setOpen(false);
          first.click();
        } else if (q.trim() && !typing) {
          nav(`/words?q=${encodeURIComponent(q.trim())}`);
        }
      }
    }
    function onDown(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onDown);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onDown);
    };
  }, [q, nav]);

  useEffect(() => {
    const term = q.trim();
    if (!term) {
      setWords([]);
      setSentences([]);
      setMedia([]);
      return;
    }
    setBusy(true);
    const t = window.setTimeout(async () => {
      try {
        const [cards, media] = await Promise.all([api.listCards(term), api.listMedia()]);
        setWords(cards.filter((c) => (c.card_type || "word") === "word").slice(0, 6));
        setSentences(cards.filter((c) => c.card_type === "sentence").slice(0, 4));
        setMedia(
          media
            .filter((m) => m.title.toLowerCase().includes(term.toLowerCase()))
            .slice(0, 4),
        );
      } catch {
        /* ignore */
      } finally {
        setBusy(false);
      }
    }, 220);
    return () => window.clearTimeout(t);
  }, [q]);

  const hasResults = words.length > 0 || sentences.length > 0 || media.length > 0;

  return (
    <div className="gs-wrap" ref={boxRef}>
      <span className="gs-icon">⌕</span>
      <input
        ref={inputRef}
        className="gs-input"
        placeholder="搜索视频、单词…"
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
      />
      <span className="gs-kbd">Ctrl K</span>

      {open && q.trim() !== "" && (
        <div className="gs-drop">
          {busy && !hasResults && <div className="gs-empty">搜索中…</div>}
          {!busy && !hasResults && <div className="gs-empty">没有匹配的视频或单词</div>}
          {words.length > 0 && <div className="gs-group">单词 · 回车或点击查看图谱</div>}
          {words.map((w) => (
            <Link
              key={w.id}
              to={`/graph?word=${encodeURIComponent(w.headword)}`}
              className="gs-row"
              onClick={() => setOpen(false)}
            >
              <span className="gs-word">{w.headword}</span>
              <span className="gs-sub">{w.meaning_zh}</span>
            </Link>
          ))}
          {sentences.length > 0 && <div className="gs-group">句库</div>}
          {sentences.map((s) => (
            <Link
              key={s.id}
              to={`/sentences?q=${encodeURIComponent(s.headword.slice(0, 40))}`}
              className="gs-row"
              onClick={() => setOpen(false)}
            >
              <span className="gs-word">{s.headword}</span>
              <span className="gs-sub">{s.meaning_zh}</span>
            </Link>
          ))}
          {media.length > 0 && <div className="gs-group">视频</div>}
          {media.map((m) => (
            <Link
              key={m.id}
              to={`/media/${m.id}`}
              className="gs-row"
              onClick={() => setOpen(false)}
            >
              <span className="gs-word">{m.title}</span>
              <span className="gs-sub">{m.segment_count} 句</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
