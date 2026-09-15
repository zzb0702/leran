import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { MouseEvent as ReactMouseEvent } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, getToken, MediaItem, Segment } from "../api";

function fmt(ms: number) {
  const s = Math.max(0, ms) / 1000;
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

export default function Workbench() {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const seekMs = Number(searchParams.get("t") || 0);
  const mediaId = Number(id);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [media, setMedia] = useState<MediaItem | null>(null);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [activeIdx, setActiveIdx] = useState(0);
  const [selectedWord, setSelectedWord] = useState("");
  const [editEn, setEditEn] = useState("");
  const [editZh, setEditZh] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loop, setLoop] = useState(false);
  const [mineMsg, setMineMsg] = useState("");
  const [dictation, setDictation] = useState(false);
  const [typed, setTyped] = useState("");
  const [dictationResult, setDictationResult] = useState<null | boolean>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  /** both | en | zh | off */
  const [subMode, setSubMode] = useState<"both" | "en" | "zh" | "off">("both");
  const [theater, setTheater] = useState(false);
  const DEFAULT_SUB_POS = { x: 50, y: 78 };
  // Overlay position as % of stage (left, top)
  const [subPos, setSubPos] = useState<{ x: number; y: number }>(() => {
    try {
      const raw = localStorage.getItem("leran_sub_pos");
      if (raw) {
        const p = JSON.parse(raw) as { x: number; y: number };
        if (
          typeof p.x === "number" &&
          typeof p.y === "number" &&
          Number.isFinite(p.x) &&
          Number.isFinite(p.y)
        ) {
          // Old overlay coords / bad drags often stick to top-right — reject those.
          const x = Math.min(92, Math.max(8, p.x));
          const y = Math.min(92, Math.max(45, p.y));
          return { x, y };
        }
      }
    } catch {
      /* ignore */
    }
    return { ...DEFAULT_SUB_POS };
  });
  const [dragging, setDragging] = useState(false);
  const dragRef = useRef<{ offsetX: number; offsetY: number } | null>(null);
  const hoverTimerRef = useRef<number | null>(null);
  const dictCloseTimerRef = useRef<number | null>(null);
  const [hoverWord, setHoverWord] = useState<string | null>(null);
  const [dict, setDict] = useState<{
    word: string;
    x: number;
    y: number;
    loading: boolean;
    deepLoading: boolean;
    data: null | {
      ipa: string;
      pos: string;
      meaning_zh: string;
      meaning_en: string;
      example_en: string;
      in_card: boolean;
      card_id: number | null;
      source: string;
    };
    error: string;
  } | null>(null);
  const dictKeepRef = useRef(false);

  function clearHoverTimer() {
    if (hoverTimerRef.current) {
      window.clearTimeout(hoverTimerRef.current);
      hoverTimerRef.current = null;
    }
  }

  function clearDictCloseTimer() {
    if (dictCloseTimerRef.current) {
      window.clearTimeout(dictCloseTimerRef.current);
      dictCloseTimerRef.current = null;
    }
  }

  function closeDict() {
    dictKeepRef.current = false;
    setDict(null);
    setHoverWord(null);
  }

  async function fetchLookup(word: string, segId: number | undefined, clientX: number, clientY: number) {
    const stage = stageRef.current;
    if (!stage) return;
    const rect = stage.getBoundingClientRect();
    const x = Math.min(rect.width - 16, Math.max(8, clientX - rect.left));
    const y = Math.max(8, clientY - rect.top - 12);
    setDict({ word, x, y, loading: true, deepLoading: false, data: null, error: "" });
    try {
      const r = await api.lookupWord(word, segId, false);
      setDict((prev) =>
        prev && prev.word === word
          ? {
              ...prev,
              loading: false,
              data: {
                ipa: r.ipa,
                pos: r.pos,
                meaning_zh: r.meaning_zh,
                meaning_en: r.meaning_en,
                example_en: r.example_en,
                in_card: r.in_card,
                card_id: r.card_id,
                source: r.source,
              },
            }
          : prev,
      );
    } catch (e) {
      setDict((prev) =>
        prev && prev.word === word
          ? {
              ...prev,
              loading: false,
              data: null,
              error: e instanceof Error ? e.message : "查询失败",
            }
          : prev,
      );
    }
  }

  async function fetchDeepZh() {
    if (!dict || !active) return;
    setDict((p) => (p ? { ...p, deepLoading: true } : p));
    try {
      const r = await api.lookupWord(dict.word, active.id, true);
      setDict((p) =>
        p && p.data
          ? {
              ...p,
              deepLoading: false,
              data: { ...p.data, meaning_zh: r.meaning_zh || p.data.meaning_zh, source: r.source },
            }
          : p,
      );
    } catch {
      setDict((p) => (p ? { ...p, deepLoading: false } : p));
    }
  }

  function onWordEnter(e: ReactMouseEvent<HTMLSpanElement>, word: string) {
    const clean = word.replace(/[^\w'-]/g, "");
    if (!clean) return;
    clearHoverTimer();
    clearDictCloseTimer();
    setHoverWord(clean.toLowerCase());
    const clientX = e.clientX;
    const clientY = e.clientY;
    const segId = active?.id;
    hoverTimerRef.current = window.setTimeout(() => {
      dictKeepRef.current = true;
      void fetchLookup(clean, segId, clientX, clientY);
    }, 800);
  }

  function onWordLeave() {
    clearHoverTimer();
    // grace period to move into the popup; otherwise auto-close it
    clearDictCloseTimer();
    dictCloseTimerRef.current = window.setTimeout(() => {
      dictCloseTimerRef.current = null;
      closeDict();
    }, 250);
  }

  useEffect(
    () => () => {
      clearHoverTimer();
      clearDictCloseTimer();
    },
    [],
  );

  useEffect(() => {
    try {
      const saved = localStorage.getItem("leran_sub_mode");
      if (saved === "both" || saved === "en" || saved === "zh" || saved === "off") {
        setSubMode(saved);
        return;
      }
      // migrate old keys
      if (localStorage.getItem("leran_sub_show") === "0") {
        setSubMode("off");
      } else {
        const lang = localStorage.getItem("leran_sub_lang");
        if (lang === "both" || lang === "en" || lang === "zh") setSubMode(lang);
      }
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    localStorage.setItem("leran_sub_pos", JSON.stringify(subPos));
  }, [subPos]);
  useEffect(() => {
    localStorage.setItem("leran_sub_mode", subMode);
  }, [subMode]);

  const active = segments[activeIdx];

  const refresh = useCallback(async () => {
    try {
      const [m, segs] = await Promise.all([api.getMedia(mediaId), api.segments(mediaId)]);
      setMedia(m);
      setSegments(segs);
      if (segs[0]) {
        setEditEn(segs[0].text_en);
        setEditZh(segs[0].text_zh);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    }
  }, [mediaId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Deep-link: /media/:id?t=12345 seeks once segments are ready.
  useEffect(() => {
    if (!segments.length || !seekMs || !videoRef.current) return;
    const video = videoRef.current;
    const idx = segments.findIndex((s) => seekMs >= s.start_ms && seekMs < s.end_ms);
    const target = idx >= 0 ? segments[idx] : segments.find((s) => s.start_ms >= seekMs) || segments[0];
    if (!target) return;
    video.currentTime = target.start_ms / 1000;
    setActiveIdx(target.idx);
  }, [segments, seekMs]);

  useEffect(() => {
    if (!media || media.status === "ready") return;
    const t = setInterval(() => {
      api.getMedia(mediaId).then((m) => {
        setMedia(m);
        if (m.status === "ready") refresh();
      });
    }, 2000);
    return () => clearInterval(t);
  }, [media, mediaId, refresh]);

  useEffect(() => {
    if (!active) return;
    setEditEn(active.text_en);
    setEditZh(active.text_zh);
    setSelectedWord("");
    setTyped("");
    setDictationResult(null);
  }, [active]);

  // Sync highlight with playback time.
  useEffect(() => {
    const video = videoRef.current;
    if (!video || !segments.length) return;
    const onTime = () => {
      const t = video.currentTime * 1000;
      let idx = segments.findIndex((s) => t >= s.start_ms && t < s.end_ms);
      if (idx < 0) {
        // nearest previous
        for (let i = segments.length - 1; i >= 0; i--) {
          if (t >= segments[i].start_ms) {
            idx = i;
            break;
          }
        }
      }
      if (idx >= 0) setActiveIdx(idx);
      if (loop && active) {
        if (t >= active.end_ms / 1000) {
          video.currentTime = active.start_ms / 1000;
        }
      }
    };
    video.addEventListener("timeupdate", onTime);
    return () => video.removeEventListener("timeupdate", onTime);
  }, [segments, loop, active]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === "j" || e.key === "J") {
        e.preventDefault();
        jump(activeIdx + 1);
      } else if (e.key === "k" || e.key === "K") {
        e.preventDefault();
        jump(activeIdx - 1);
      } else if (e.key === "l" || e.key === "L") {
        e.preventDefault();
        replay();
      } else if (e.key === "a" || e.key === "A") {
        e.preventDefault();
        void mine();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  function jump(idx: number) {
    const seg = segments[Math.max(0, Math.min(segments.length - 1, idx))];
    if (!seg || !videoRef.current) return;
    setActiveIdx(seg.idx);
    videoRef.current.currentTime = seg.start_ms / 1000;
  }

  function replay() {
    if (!active || !videoRef.current) return;
    videoRef.current.currentTime = active.start_ms / 1000;
    videoRef.current.play();
  }

  function onSubPointerDown(e: ReactMouseEvent) {
    if (e.button !== 0) return;
    const stage = stageRef.current;
    if (!stage) return;
    e.preventDefault();
    e.stopPropagation();
    closeDict();
    clearHoverTimer();
    const rect = stage.getBoundingClientRect();
    const xPct = ((e.clientX - rect.left) / rect.width) * 100;
    const yPct = ((e.clientY - rect.top) / rect.height) * 100;
    dragRef.current = { offsetX: xPct - subPos.x, offsetY: yPct - subPos.y };
    setDragging(true);

    const onMove = (ev: MouseEvent) => {
      if (!dragRef.current || !stageRef.current) return;
      const r = stageRef.current.getBoundingClientRect();
      const nx = ((ev.clientX - r.left) / r.width) * 100 - dragRef.current.offsetX;
      const ny = ((ev.clientY - r.top) / r.height) * 100 - dragRef.current.offsetY;
      setSubPos({
        x: Math.min(92, Math.max(8, nx)),
        y: Math.min(90, Math.max(40, ny)),
      });
    };
    const onUp = () => {
      dragRef.current = null;
      setDragging(false);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }

  async function saveEdits() {
    if (!active) return;
    try {
      await api.updateSegment(active.id, { edited_en: editEn, edited_zh: editZh });
      setMessage("已保存");
      await refresh();
      setTimeout(() => setMessage(""), 1500);
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存失败");
    }
  }

  async function mine() {
    if (!active) return;
    const word = (selectedWord || editEn.trim().split(/\s+/)[0] || "").replace(/[^\w'-]/g, "");
    if (!word) {
      setMineMsg("先选中一个词");
      return;
    }
    try {
      await api.cardFromSegment(active.id, word);
      setMineMsg(`已入卡：${word.toLowerCase()}`);
      setTimeout(() => setMineMsg(""), 2000);
    } catch (e) {
      setMineMsg(e instanceof Error ? e.message : "入卡失败");
    }
  }

  const words = useMemo(() => {
    if (active?.words?.length) return active.words.map((w) => w.text);
    return (active?.text_en || "").split(/\s+/).filter(Boolean);
  }, [active]);

  if (error) return <p className="error-text">{error}</p>;
  if (!media) return <p className="muted">加载中…</p>;

  function renderWordTokens(text: string) {
    return text.split(/(\s+)/).map((tok, i) => {
      if (!tok.trim()) return <span key={i}>{tok}</span>;
      const clean = tok.replace(/[^\w'-]/g, "");
      const isHover = clean && hoverWord === clean.toLowerCase();
      return (
        <span
          key={i}
          className={`sub-word${isHover ? " active" : ""}`}
          onMouseEnter={(e) => onWordEnter(e, tok)}
          onMouseLeave={onWordLeave}
        >
          {tok}
        </span>
      );
    });
  }

  return (
    <div className="workbench-page">
      <div className="wb-top">
        <div>
          <div className="muted small">
            <Link to="/library">← 媒体库</Link>
          </div>
          <h1 className="page-title" style={{ marginBottom: 4 }}>
            {media.title}
          </h1>
          <p className="page-sub" style={{ marginBottom: 0 }}>
            {media.status === "ready"
              ? "J/K 换句 · L 重播 · A 入卡 · 悬停 3 秒查词"
              : `处理中：${media.status}${media.progress ? ` · ${media.progress}` : ""}`}
          </p>
        </div>
        <div className="row">
          <button className="btn" onClick={() => api.downloadExport(media.id, "srt", "bilingual")}>
            导出双语 SRT
          </button>
          <button className="btn" onClick={() => api.downloadExport(media.id, "srt", "en")}>
            仅英文
          </button>
          <button className="btn" onClick={() => setTheater((v) => !v)}>
            {theater ? "显示字幕栏" : "影院模式"}
          </button>
        </div>
      </div>

      {media.status !== "ready" && (
        <div className="card-box" style={{ marginBottom: 12 }}>
          {media.status === "failed" ? (
            <>
              <div className="error-text">失败：{media.error}</div>
              <button className="btn" style={{ marginTop: 8 }} onClick={() => api.reprocess(media.id)}>
                重跑识别
              </button>
            </>
          ) : (
            <div className="muted">
              流水线进行中。45 分钟剧集可能需要数分钟到更久，可离开本页。
            </div>
          )}
        </div>
      )}

      <div className={`wb-shell${theater ? " theater" : ""}`}>
        <div className="wb-player-col">
          <div className="player-stage" ref={stageRef}>
            <video
              ref={videoRef}
              controls
              src={`/api/media/${media.id}/file?token=${encodeURIComponent(getToken() || "")}`}
              preload="metadata"
            />
            {subMode !== "off" && active && !dictation && (
              <div
                className={`cinema-subs${dragging ? " dragging" : ""}`}
                style={{
                  left: `${subPos.x}%`,
                  top: `${subPos.y}%`,
                  transform: "translateX(-50%)",
                }}
                onMouseDown={onSubPointerDown}
                title="左键按住拖动 · 悬停单词约 1 秒查词"
              >
                {(subMode === "both" || subMode === "en") && (
                  <div className="cinema-en">{renderWordTokens(active.text_en)}</div>
                )}
                {(subMode === "both" || subMode === "zh") && active.text_zh && (
                  <div className="cinema-zh">{active.text_zh}</div>
                )}
              </div>
            )}
            {dict && (
              <div
                className="dict-popup"
                style={{
                  left: Math.max(8, dict.x - 40),
                  top: Math.max(8, dict.y - 12),
                  transform: `translate(0, -100%)`,
                  position: "absolute",
                }}
                onMouseEnter={() => {
                  dictKeepRef.current = true;
                  clearHoverTimer();
                  clearDictCloseTimer();
                }}
                onMouseLeave={() => {
                  dictKeepRef.current = false;
                  closeDict();
                }}
              >
                <div className="dict-head">
                  <div className="dict-word">{dict.word}</div>
                  <button className="btn btn-ghost small" onClick={closeDict} type="button">
                    关闭
                  </button>
                </div>
                {dict.loading && <div className="dict-loading">查询中…</div>}
                {!dict.loading && dict.error && <div className="error-text small">{dict.error}</div>}
                {!dict.loading && dict.data && (
                  <>
                    {dict.data.ipa && (
                      <div className="dict-meta">
                        <span className="dict-chip">{dict.data.ipa}</span>
                        {dict.data.in_card && <span className="dict-chip">已在词库</span>}
                      </div>
                    )}
                    <div className="dict-meaning">
                      {dict.data.pos && <span className="dict-pos">{dict.data.pos}</span>}
                      {dict.data.meaning_zh || dict.data.meaning_en || "（暂无释义）"}
                    </div>
                    {!dict.data.meaning_zh && (
                      <button
                        type="button"
                        className="btn small"
                        style={{ marginTop: 8 }}
                        disabled={dict.deepLoading}
                        onClick={fetchDeepZh}
                      >
                        {dict.deepLoading ? "翻译中…" : "生成中文释义"}
                      </button>
                    )}
                    {dict.data.example_en && <div className="dict-example">{dict.data.example_en}</div>}
                    <div className="dict-actions">
                      <button
                        type="button"
                        className="btn"
                        onClick={async () => {
                          if (!active) return;
                          await api.cardFromSegment(active.id, dict.word);
                          setDict((p) =>
                            p && p.data ? { ...p, data: { ...p.data, in_card: true } } : p,
                          );
                          setMineMsg(`已入卡：${dict.word.toLowerCase()}`);
                          setTimeout(() => setMineMsg(""), 2000);
                        }}
                      >
                        入卡
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>

          <div className="wb-tools">
            <button className="btn small" onClick={replay}>
              重播本句
            </button>
            <label className="row" style={{ gap: 6 }}>
              <input type="checkbox" checked={loop} onChange={(e) => setLoop(e.target.checked)} />
              句循环
            </label>
            <label className="row" style={{ gap: 6 }}>
              <input
                type="checkbox"
                checked={dictation}
                onChange={(e) => setDictation(e.target.checked)}
              />
              听写
            </label>
            <label className="row" style={{ gap: 6 }}>
              字幕
              <select
                value={subMode}
                onChange={(e) => setSubMode(e.target.value as "both" | "en" | "zh" | "off")}
              >
                <option value="both">英中双语</option>
                <option value="en">仅英文</option>
                <option value="zh">仅中文</option>
                <option value="off">全隐藏</option>
              </select>
            </label>
            <button
              className="btn small"
              onClick={() => {
                setSubPos({ ...DEFAULT_SUB_POS });
                localStorage.setItem("leran_sub_pos", JSON.stringify(DEFAULT_SUB_POS));
              }}
            >
              字幕复位
            </button>
            {mineMsg && <span>{mineMsg}</span>}
            <span style={{ flex: 1 }} />
            <button className="btn btn-fill small" onClick={mine} disabled={!active}>
              入卡
            </button>
          </div>

          {dictation && active && (
            <div className="card-box" style={{ borderRadius: 0, borderLeft: 0, borderRight: 0 }}>
              <div className="muted small" style={{ marginBottom: 8 }}>
                听写：听本句，输入英文后对照
              </div>
              <textarea
                rows={2}
                value={typed}
                onChange={(e) => setTyped(e.target.value)}
                placeholder="Type what you hear..."
                style={{
                  width: "100%",
                  background: "#1a1a1a",
                  color: "#e8e8e2",
                  border: "1px solid #333",
                  borderRadius: 6,
                  padding: 8,
                }}
              />
              <div className="row" style={{ marginTop: 8 }}>
                <button className="btn" onClick={replay}>
                  再听一遍
                </button>
                <button
                  className="btn btn-fill"
                  onClick={() => {
                    const norm = (s: string) =>
                      s
                        .toLowerCase()
                        .replace(/[^\w\s']/g, " ")
                        .replace(/\s+/g, " ")
                        .trim();
                    setDictationResult(norm(typed) === norm(active.text_en));
                  }}
                >
                  对照
                </button>
                {dictationResult === true && <span style={{ color: "#6dcea0" }}>正确</span>}
                {dictationResult === false && (
                  <span className="error-text">不一致 · 参考：{active.text_en}</span>
                )}
              </div>
            </div>
          )}
        </div>

        <aside className="wb-transcript">
          <div className="wb-transcript-head">字幕 · {segments.length}</div>
          {segments.length === 0 && (
            <div className="empty" style={{ padding: 16 }}>
              字幕尚未就绪。
            </div>
          )}
          {segments.map((s, i) => (
            <div
              key={s.id}
              className={`wb-cue${i === activeIdx ? " active" : ""}`}
              onClick={() => jump(i)}
            >
              <div className="wb-cue-time">{fmt(s.start_ms)}</div>
              <div className="wb-cue-en">
                {dictation && i === activeIdx ? "（听写中…）" : s.text_en}
              </div>
              <div className="wb-cue-zh">{dictation && i === activeIdx ? "" : s.text_zh}</div>
            </div>
          ))}
          {active && (
            <div className="wb-editor">
              <div className="muted small" style={{ marginBottom: 6 }}>
                校对当前句
              </div>
              <textarea
                rows={2}
                value={editEn}
                onChange={(e) => setEditEn(e.target.value)}
              />
              <textarea
                rows={2}
                value={editZh}
                onChange={(e) => setEditZh(e.target.value)}
              />
              <div className="row">
                <button className="btn small" onClick={saveEdits}>
                  保存
                </button>
                {message && <span className="small">{message}</span>}
              </div>
              <div className="muted small" style={{ margin: "10px 0 6px" }}>
                点词入卡
              </div>
              <div>
                {words.map((w, i) => {
                  const clean = w.replace(/[^\w'-]/g, "");
                  const selected =
                    selectedWord && clean.toLowerCase() === selectedWord.toLowerCase();
                  return (
                    <span
                      key={`${w}-${i}`}
                      className={`word-chip${selected ? " selected" : ""}`}
                      onClick={() => clean && setSelectedWord(clean)}
                    >
                      {w}
                    </span>
                  );
                })}
              </div>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
