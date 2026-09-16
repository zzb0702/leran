import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, ReviewItem } from "../api";
import { dayKeyLabel, localDayKey } from "../dates";

const LABELS: Record<number, string> = {
  1: "1 Again",
  2: "2 Hard",
  3: "3 Good",
  4: "4 Easy",
};

type Mode = "std" | "rev" | "spell" | "listen";

const MODES: { id: Mode; label: string; hint: string }[] = [
  { id: "std", label: "标准", hint: "看单词，想中文意思" },
  { id: "rev", label: "反向", hint: "看中文意思，想单词" },
  { id: "spell", label: "拼写", hint: "看中文意思，键盘拼出单词" },
  { id: "listen", label: "听音", hint: "听原声，想单词（需音频切片）" },
];

/** days → "15分" / "12小时" / "3天" / "2.5月" for answer-button hints (Anki style). */
function fmtInterval(days: number): string {
  if (days <= 0) return "—";
  const minutes = days * 24 * 60;
  if (minutes < 60) return `${Math.max(1, Math.round(minutes))}分`;
  if (days < 1) return `${Math.round(days * 24)}小时`;
  if (days < 30) return `${Math.round(days)}天`;
  if (days < 365) return `${(days / 30).toFixed(days < 90 ? 1 : 0)}月`;
  return `${(days / 365).toFixed(1)}年`;
}

/** Char-level diff between typed answer and the headword. */
function DiffText({ typed, target }: { typed: string; target: string }) {
  const a = (typed || "").toLowerCase();
  const b = (target || "").toLowerCase();
  const n = Math.max(a.length, b.length);
  const parts: { ch: string; ok: boolean }[] = [];
  for (let i = 0; i < n; i++) {
    parts.push({ ch: b[i] ?? "·", ok: a[i] === b[i] });
  }
  return (
    <span style={{ fontFamily: "var(--serif)", fontSize: 22, letterSpacing: 0.02 }}>
      {parts.map((p, i) => (
        <span
          key={i}
          style={
            p.ok
              ? { color: "var(--accent-strong)" }
              : { color: "var(--error)", borderBottom: "2px solid var(--error)" }
          }
        >
          {p.ch}
        </span>
      ))}
    </span>
  );
}

export default function Review() {
  const [searchParams] = useSearchParams();
  const day = searchParams.get("day") || "";
  const [mode, setMode] = useState<Mode>(() => {
    const saved = localStorage.getItem("leran_review_mode");
    return saved === "rev" || saved === "spell" || saved === "listen" ? saved : "std";
  });
  const [queue, setQueue] = useState<ReviewItem[]>([]);
  const [revealed, setRevealed] = useState(false);
  const [typed, setTyped] = useState("");
  const [typedSubmitted, setTypedSubmitted] = useState(false);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [startedAt, setStartedAt] = useState(Date.now());
  const [session, setSession] = useState({ done: 0, again: 0, startedAt: Date.now() });
  const [audioOk, setAudioOk] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const typedRef = useRef<HTMLInputElement | null>(null);

  const item = queue[0];
  const card = item?.card;
  const isSentence = card?.card_type === "sentence";
  const totalLeft = session.done + queue.length;
  const typedCorrect =
    !!card && typedSubmitted && typed.trim().toLowerCase() === card.headword.toLowerCase();
  const displayMode: Mode = isSentence && mode === "spell" ? "std" : mode;

  async function load() {
    try {
      const q = await api.reviewQueue(day ? 200 : 20);
      setQueue(day ? q.filter((it) => localDayKey(it.card.created_at) === day) : q);
      setRevealed(false);
      setTyped("");
      setTypedSubmitted(false);
      setStartedAt(Date.now());
      setSession({ done: 0, again: 0, startedAt: Date.now() });
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [day]);

  useEffect(() => {
    localStorage.setItem("leran_review_mode", mode);
    setRevealed(false);
    setTyped("");
    setTypedSubmitted(false);
  }, [mode]);

  // Audio availability per card; autoplay in listening mode.
  useEffect(() => {
    setAudioOk(false);
    if (!item?.card.audio_clip_key) return;
    const url = api.cardAudioUrl(item.card.id);
    fetch(url)
      .then((r) => {
        setAudioOk(r.ok);
        if (r.ok && mode === "listen") audioRef.current?.play().catch(() => undefined);
      })
      .catch(() => setAudioOk(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [item?.card.id, mode]);

  // Focus the typing box in spelling mode.
  useEffect(() => {
    if (mode === "spell" && !revealed) typedRef.current?.focus();
  }, [mode, revealed, item?.card.id]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === " " || e.code === "Space") {
        e.preventDefault();
        if (mode !== "spell" || revealed) setRevealed(true);
      } else if (e.key === "p" || e.key === "P") {
        e.preventDefault();
        audioRef.current?.play().catch(() => undefined);
      } else if (["1", "2", "3", "4"].includes(e.key) && revealed) {
        e.preventDefault();
        void rate(Number(e.key));
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [revealed, queue, mode]);

  async function rate(rating: number) {
    const cur = queue[0];
    if (!cur) return;
    try {
      await api.submitReview(cur.card.id, rating, Date.now() - startedAt);
      setSession((s) => ({
        ...s,
        done: s.done + 1,
        again: s.again + (rating === 1 ? 1 : 0),
      }));
      // Anki behavior: an "Again" card comes back within this session.
      setQueue((prev) => (rating === 1 ? [...prev.slice(1), cur] : prev.slice(1)));
      setRevealed(false);
      setTyped("");
      setTypedSubmitted(false);
      setStartedAt(Date.now());
      setMsg("");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "提交失败");
    }
  }

  const activeMode = useMemo(() => MODES.find((m) => m.id === mode)!, [mode]);

  const audioBlock = card?.audio_clip_key ? (
    <div style={{ marginTop: 14 }}>
      <button className="btn" onClick={() => audioRef.current?.play().catch(() => undefined)}>
        播放原声 · P
      </button>
      <audio
        ref={audioRef}
        src={api.cardAudioUrl(card.id)}
        preload={mode === "listen" ? "auto" : "none"}
        style={{ display: "none" }}
      />
    </div>
  ) : null;

  if (error) return <p className="error-text">{error}</p>;

  return (
    <div>
      <h1 className="page-title">复习</h1>
      <p className="page-sub">
        {activeMode.hint} · Space 揭晓 · 1–4 评分 · P 听原声
        {totalLeft > 0 && (
          <>
            {" "}
            · 进度 {session.done} / {totalLeft}
          </>
        )}
      </p>

      <div className="row" style={{ gap: 6, marginBottom: 8 }}>
        {MODES.filter((m) => !(isSentence && m.id === "spell")).map((m) => (
          <button
            key={m.id}
            className={`btn small${displayMode === m.id ? " btn-fill" : ""}`}
            onClick={() => setMode(m.id)}
            title={m.hint}
          >
            {m.label}
          </button>
        ))}
        {isSentence && <span className="muted small">句卡 · 拼写模式不适用</span>}
      </div>

      {day && (
        <div className="row" style={{ marginBottom: 12 }}>
          <span className="small" style={{ color: "var(--accent)" }}>
            正在只复习「{dayKeyLabel(day)}」收录的词
          </span>
          <Link to="/review" className="small" style={{ color: "var(--accent)" }}>
            切回全部队列
          </Link>
        </div>
      )}

      {!card ? (
        session.done > 0 ? (
          <div className="card-box" style={{ textAlign: "center", padding: 40 }}>
            <div
              style={{
                fontFamily: "var(--serif)",
                fontSize: 24,
                fontWeight: 600,
                marginBottom: 6,
              }}
            >
              本轮完成 🎉
            </div>
            <p className="muted" style={{ marginTop: 0 }}>
              复习 {session.done} 张 · 忘记 {session.again} 张 · 用时{" "}
              {Math.round((Date.now() - session.startedAt) / 1000)} 秒 · 平均{" "}
              {Math.round((Date.now() - session.startedAt) / 1000 / session.done)} 秒/张
            </p>
            <div className="row" style={{ justifyContent: "center", marginTop: 8 }}>
              <button className="btn btn-fill" onClick={() => void load()}>
                再拉一轮
              </button>
              <Link className="btn" to="/words">
                回词库
              </Link>
              <Link className="btn" to="/">
                回首页
              </Link>
            </div>
          </div>
        ) : (
          <div className="empty">
            {day ? <>这一天没有待复习的词。</> : <>今日队列已清空。</>} 去{" "}
            <Link to="/library" style={{ color: "var(--accent)" }}>
              媒体库
            </Link>{" "}
            从字幕入新卡。
          </div>
        )
      ) : (
        <div className="card-box">
          <div className="review-stage">
            <div>
              {/* —— front side by mode —— */}
              {displayMode === "std" && (
                <>
                  <div className={`review-word${isSentence ? " sentence" : ""}`}>
                    {card.headword}
                  </div>
                  {card.pos && !isSentence && <div className="muted">{card.pos}</div>}
                  {audioBlock}
                </>
              )}

              {displayMode === "rev" && (
                <>
                  <div className="review-word" style={{ fontSize: isSentence ? 28 : 30 }}>
                    {card.meaning_zh || "（暂无释义）"}
                  </div>
                  {card.pos && !isSentence && <div className="muted small">词性 {card.pos}</div>}
                </>
              )}

              {displayMode === "listen" && (
                <>
                  <div className="review-word" style={{ fontSize: 26, color: "var(--n-500)" }}>
                    🎧 {isSentence ? "听音辨句" : "听音辨词"}
                  </div>
                  {audioBlock ? (
                    <p className="muted small" style={{ marginTop: 10 }}>
                      已自动播放，可按 P 重听
                    </p>
                  ) : (
                    <p className="muted small" style={{ marginTop: 10 }}>
                      这张卡没有音频切片（入卡时未装 ffmpeg），本次直接显示{isSentence ? "句子" : "单词"}
                    </p>
                  )}
                </>
              )}

              {displayMode === "spell" && !typedSubmitted && (
                <>
                  <div className="review-word" style={{ fontSize: 30 }}>
                    {card.meaning_zh || "（暂无释义）"}
                  </div>
                  {card.pos && <div className="muted small">词性 {card.pos}</div>}
                  <input
                    ref={typedRef}
                    value={typed}
                    onChange={(e) => setTyped(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        setTypedSubmitted(true);
                        setRevealed(true);
                      }
                    }}
                    placeholder="输入英文单词，回车提交"
                    autoComplete="off"
                    autoCapitalize="off"
                    spellCheck={false}
                    style={{
                      marginTop: 18,
                      fontSize: 18,
                      padding: "10px 14px",
                      width: 280,
                      textAlign: "center",
                      border: "1px solid var(--n-100)",
                      borderRadius: "var(--radius-s)",
                    }}
                  />
                  {card.audio_clip_key && (
                    <div style={{ marginTop: 12 }}>
                      <button
                        className="btn small"
                        onClick={() => audioRef.current?.play().catch(() => undefined)}
                      >
                        提示音 · P
                      </button>
                      <audio
                        ref={audioRef}
                        src={api.cardAudioUrl(card.id)}
                        preload="none"
                        style={{ display: "none" }}
                      />
                    </div>
                  )}
                </>
              )}

              {/* —— reveal —— */}
              {(revealed || (displayMode === "spell" && typedSubmitted)) && (
                <>
                  {displayMode === "spell" ? (
                    <div style={{ marginTop: 18 }}>
                      <div style={{ marginBottom: 8 }}>
                        <DiffText typed={typed} target={card.headword} />
                      </div>
                      <div className={typedCorrect ? "" : "error-text"} style={{ fontWeight: 600 }}>
                        {typedCorrect ? "✓ 拼写正确" : `✗ 正确拼写：${card.headword}`}
                      </div>
                      <div className="review-meaning">{card.meaning_zh || "（暂无释义）"}</div>
                    </div>
                  ) : (
                    <>
                      {displayMode !== "std" && (
                        <div
                          className={`review-word${isSentence ? " sentence" : ""}`}
                          style={{ marginTop: 16 }}
                        >
                          {card.headword}
                        </div>
                      )}
                      {displayMode === "std" ? (
                        <div className="review-meaning">
                          {card.meaning_zh || card.example_zh || "（暂无释义）"}
                        </div>
                      ) : (
                        <div className="muted" style={{ fontSize: 15 }}>
                          {card.meaning_zh}
                        </div>
                      )}
                      {displayMode === "listen" && !audioOk && card.audio_clip_key && (
                        <div
                          className={`review-word${isSentence ? " sentence" : ""}`}
                          style={{ marginTop: 16 }}
                        >
                          {card.headword}
                        </div>
                      )}
                    </>
                  )}
                  {!isSentence && card.example_en && <p className="review-example">{card.example_en}</p>}
                  {!isSentence && card.example_zh && <p className="review-example">{card.example_zh}</p>}
                  <div className="muted small" style={{ marginTop: 4 }}>
                    间隔 {fmtInterval(card.interval_days ?? 0)} · 难度{" "}
                    {(card.ease ?? 2.5).toFixed(2)} · 遗忘 {card.lapses ?? 0} 次 · 已学{" "}
                    {card.reps ?? 0} 遍
                  </div>
                  {card.media_id != null && (
                    <Link
                      className="btn small"
                      to={`/media/${card.media_id}?t=${item.t_ms}`}
                      style={{ marginTop: 10 }}
                    >
                      跳到原句{" "}
                      {Math.floor(item.t_ms / 60000)}:
                      {String(Math.floor((item.t_ms % 60000) / 1000)).padStart(2, "0")}
                    </Link>
                  )}

                  {!revealed && displayMode === "spell" && (
                    <div className="kbd-row">
                      <button className="kbd" onClick={() => setRevealed(true)}>
                        看完整卡片 · Space
                      </button>
                    </div>
                  )}
                  {revealed && (
                    <div className="kbd-row">
                      {[1, 2, 3, 4].map((r) => (
                        <button key={r} className="kbd" onClick={() => rate(r)}>
                          <span>{LABELS[r]}</span>
                          {item.interval_previews && (
                            <span className="kbd-hint">
                              {fmtInterval(item.interval_previews[r - 1] ?? 0)}
                            </span>
                          )}
                        </button>
                      ))}
                    </div>
                  )}
                  {msg && <p className="error-text">{msg}</p>}
                </>
              )}

              {displayMode !== "spell" && !revealed && (
                <button
                  className="btn"
                  style={{ marginTop: 26 }}
                  onClick={() => setRevealed(true)}
                >
                  显示答案 · Space
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
