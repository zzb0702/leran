import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, Card, Story } from "../api";
import { dayKeyLabel, localDayKey, parseCreated } from "../dates";

type StatusTab = "all" | "new" | "learning" | "review";

const STATUS_TABS: { id: StatusTab; label: string }[] = [
  { id: "all", label: "全部" },
  { id: "new", label: "新词" },
  { id: "learning", label: "学习中" },
  { id: "review", label: "已掌握" },
];

function BoldWord({ text, word }: { text: string; word: string }) {
  if (!text) return null;
  const re = new RegExp(`(${word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\w*)`, "ig");
  return (
    <>
      {text.split(re).map((p, i) =>
        p && p.toLowerCase().startsWith(word.toLowerCase()) ? (
          <strong key={i} style={{ color: "var(--accent-strong)" }}>
            {p}
          </strong>
        ) : (
          <span key={i}>{p}</span>
        ),
      )}
    </>
  );
}

function dueLabel(dueAt: string): string {
  const due = parseCreated(dueAt);
  const now = new Date();
  if (due <= now) return "现在";
  const mins = (due.getTime() - now.getTime()) / 60000;
  if (mins < 60) return `${Math.max(1, Math.round(mins))}分后`;
  const days = Math.round(mins / 1440);
  if (days < 1) return `${Math.round(mins / 60)}小时后`;
  if (days === 1) return "明天";
  return `${days} 天后`;
}

function stateBadge(s: string) {
  if (s === "new") return <span className="badge badge-new">新词</span>;
  if (s === "learning" || s === "relearning") return <span className="badge badge-learn">学习中</span>;
  return <span className="badge badge-done">已掌握</span>;
}

/** —— right rail: today AI story —— */
function StoryPanel({ words, hasToday }: { words: string[]; hasToday: boolean }) {
  const [stories, setStories] = useState<Story[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const todayKey = localDayKey(new Date().toISOString());

  useEffect(() => {
    api
      .stories()
      .then((all) => setStories(all.filter((s) => s.day === todayKey)))
      .catch(() => undefined);
  }, [todayKey]);

  async function generate() {
    setBusy(true);
    setMsg("");
    try {
      const s = await api.generateStory(todayKey, words);
      setStories((prev) => [s, ...prev]);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "生成失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card-box story-panel">
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
        <span style={{ fontWeight: 600, color: "var(--n-900)" }}>✦ 今日语境练习</span>
        <button className="btn small btn-fill" disabled={busy || words.length === 0} onClick={() => void generate()}>
          {busy ? "写作中…" : stories.length ? "再写一篇" : "AI 小作文"}
        </button>
      </div>
      {!hasToday && (
        <p className="muted small" style={{ marginTop: 0 }}>
          今天还没有收词，先用最近一批单词练习。
        </p>
      )}
      {msg && <p className="error-text small">{msg}</p>}
      {stories.length === 0 && !busy && (
        <p className="muted small">AI 会把这些词串成一篇英文短文（目标词加粗 + 中文翻译），语境记忆更牢。</p>
      )}
      {stories.map((s) => {
        const idx = s.content.search(/^===\s*$/m);
        const en = (idx >= 0 ? s.content.slice(0, idx) : s.content).trim();
        const zh = idx >= 0 ? s.content.slice(idx).replace(/^===\s*$/m, "").trim() : "";
        return (
          <div key={s.id} className="story-item">
            <div className="story-body">
              {en.split(/(\*\*[^*]+\*\*)/g).map((p, i) =>
                p.startsWith("**") && p.endsWith("**") ? (
                  <strong key={i} className="story-hl">
                    {p.slice(2, -2)}
                  </strong>
                ) : (
                  <span key={i}>{p}</span>
                ),
              )}
            </div>
            {zh && <div className="story-zh">{zh}</div>}
            <button
              className="btn btn-ghost small"
              onClick={async () => {
                await api.deleteStory(s.id).catch(() => undefined);
                setStories((prev) => prev.filter((x) => x.id !== s.id));
              }}
            >
              删除
            </button>
          </div>
        );
      })}
    </div>
  );
}

/** —— right rail: mini focus review —— */
function MiniReview() {
  const [item, setItem] = useState<{ id: number; word: string; ipa: string; zh: string } | null>(null);
  const [revealed, setRevealed] = useState(false);
  const [left, setLeft] = useState(0);

  async function load() {
    try {
      const q = await api.reviewQueue(1);
      const it = q[0];
      setItem(it ? { id: it.card.id, word: it.card.headword, ipa: it.card.ipa, zh: it.card.meaning_zh } : null);
      setLeft(q.length);
      setRevealed(false);
    } catch {
      setItem(null);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function rate(r: number) {
    if (!item) return;
    await api.submitReview(item.id, r).catch(() => undefined);
    void load();
  }

  return (
    <div className="card-box mini-review">
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 6 }}>
        <span style={{ fontWeight: 600, color: "var(--n-900)" }}>✦ 专注复习模式</span>
        <Link to="/review" className="small week-more">
          进入全屏 →
        </Link>
      </div>
      {!item ? (
        <p className="muted small" style={{ margin: "6px 0" }}>
          {left === 0 ? "队列已清空，今天可以休息了 ✓" : "加载中…"}
        </p>
      ) : (
        <>
          <div className="mini-progress muted small">{left} 张待复习</div>
          <div className="mini-word">
            {item.word}
            {item.ipa && <div className="muted small" style={{ fontFamily: "var(--font)" }}>{item.ipa}</div>}
          </div>
          {revealed ? (
            <div className="mini-meaning">{item.zh || "（暂无释义）"}</div>
          ) : (
            <button className="btn mini-reveal" onClick={() => setRevealed(true)}>
              显示释义 · Space
            </button>
          )}
          <div className="mini-ratings">
            {[
              { r: 1, l: "1", sub: "Again", cls: "mr-1" },
              { r: 2, l: "2", sub: "Hard", cls: "mr-2" },
              { r: 3, l: "3", sub: "Good", cls: "mr-3" },
              { r: 4, l: "4", sub: "Easy", cls: "mr-4" },
            ].map((b) => (
              <button key={b.r} className={`mini-rate ${b.cls}`} disabled={!revealed} onClick={() => void rate(b.r)}>
                <span>{b.l}</span>
                <span>{b.sub}</span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export default function Words() {
  const [searchParams] = useSearchParams();
  const [cards, setCards] = useState<Card[]>([]);
  const [tab, setTab] = useState<StatusTab>("all");
  const [q, setQ] = useState(searchParams.get("q") || "");
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({});
  const todayKey = localDayKey(new Date().toISOString());

  async function load(query = q) {
    try {
      setCards(await api.listCards(query));
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    }
  }

  useEffect(() => {
    load(q);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const groups = useMemo(() => {
    const inTab = (c: Card) => {
      if (tab === "new") return c.state === "new";
      if (tab === "learning") return c.state === "learning" || c.state === "relearning";
      if (tab === "review") return c.state === "review";
      return true;
    };
    const sorted = [...cards.filter(inTab)].sort(
      (a, b) => b.created_at.localeCompare(a.created_at) || b.id - a.id,
    );
    const map = new Map<string, Card[]>();
    for (const c of sorted) {
      const key = localDayKey(c.created_at);
      const list = map.get(key);
      if (list) list.push(c);
      else map.set(key, [c]);
    }
    return [...map.entries()];
  }, [cards, tab]);

  // right-rail story words: today's cards, else the newest group
  const storyWords = useMemo(() => {
    const today = cards.filter((c) => localDayKey(c.created_at) === todayKey);
    if (today.length > 0) return today.map((c) => c.headword);
    return groups[0]?.[1].map((c) => c.headword) ?? [];
  }, [cards, groups, todayKey]);

  function inGroupAllSelected(items: Card[]) {
    return items.length > 0 && items.every((c) => selected.has(c.id));
  }

  function toggleGroup(items: Card[]) {
    const ids = items.map((c) => c.id);
    const allIn = inGroupAllSelected(items);
    setSelected((prev) => {
      const next = new Set(prev);
      for (const id of ids) {
        if (allIn) next.delete(id);
        else next.add(id);
      }
      return next;
    });
  }

  async function removeCard(c: Card) {
    if (!window.confirm(`删除「${c.headword}」？复习进度会一并移除。`)) return;
    try {
      await api.deleteCard(c.id);
      setCards((prev) => prev.filter((x) => x.id !== c.id));
      setSelected((prev) => {
        const next = new Set(prev);
        next.delete(c.id);
        return next;
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "删除失败");
    }
  }

  async function removeSelected() {
    const ids = [...selected];
    if (ids.length === 0) return;
    if (!window.confirm(`批量删除选中的 ${ids.length} 张卡？不可恢复。`)) return;
    const failed: number[] = [];
    for (const id of ids) {
      try {
        await api.deleteCard(id);
      } catch {
        failed.push(id);
      }
    }
    setCards((prev) => prev.filter((c) => !ids.includes(c.id) || failed.includes(c.id)));
    setSelected(new Set(failed));
    if (failed.length > 0) setError(`${failed.length} 张删除失败，已保留勾选`);
  }

  return (
    <div className="words-page">
      <div className="words-main">
        <h1 className="page-title">词库</h1>
        <p className="page-sub">从真实视频语境中收集的单词，按入卡日期分组，让学习贴近真实世界。</p>

        <div className="row words-tabs" style={{ gap: 2, marginBottom: 16 }}>
          {STATUS_TABS.map((t) => (
            <button
              key={t.id}
              className={`words-tab${tab === t.id ? " active" : ""}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
          <Link to="/graph" className="words-tab words-tab-link">
            单词图谱 →
          </Link>
        </div>

        <div className="row" style={{ marginBottom: 16, flexWrap: "wrap", gap: 8 }}>
          <input
            placeholder="搜索单词…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void load();
            }}
            className="words-search"
          />
          <button className="btn" onClick={() => load()}>
            搜索
          </button>
          <div style={{ flex: 1 }} />
          <button className="btn" onClick={() => api.exportAnkiTsv().catch((e) => setError(e.message))}>
            导出 Anki TSV
          </button>
          <button className="btn" onClick={() => api.exportAnkiZip().catch((e) => setError(e.message))}>
            导出 Anki ZIP（含音频）
          </button>
          <button className="btn" onClick={() => api.exportCardsCsv().catch((e) => setError(e.message))}>
            导出 CSV
          </button>
        </div>

        {error && <p className="error-text">{error}</p>}

        {selected.size > 0 && (
          <div className="row" style={{ marginBottom: 12, gap: 8 }}>
            <span className="small" style={{ fontWeight: 600 }}>
              已选 {selected.size} 张
            </span>
            <button className="btn small btn-danger" onClick={() => void removeSelected()}>
              批量删除
            </button>
            <button className="btn small" onClick={() => setSelected(new Set())}>
              取消选择
            </button>
          </div>
        )}

        {cards.length === 0 ? (
          <div className="empty">还没有词。打开一个视频，在当前句点词入卡。</div>
        ) : (
          groups.map(([key, items], gi) => {
            const open = openGroups[key] ?? gi === 0;
            const isNew = items.filter((c) => c.state === "new").length;
            const learning = items.filter(
              (c) => c.state === "learning" || c.state === "relearning",
            ).length;
            const reviewed = items.filter((c) => c.state === "review").length;
            const pct = items.length > 0 ? Math.round(((learning + reviewed) / items.length) * 100) : 0;
            return (
              <div key={key} className="word-group">
                <button
                  className="word-group-head"
                  onClick={() => setOpenGroups((o) => ({ ...o, [key]: !o[key] }))}
                >
                  <span className="word-group-caret">{open ? "▾" : "▸"}</span>
                  <span className="word-group-day">{dayKeyLabel(key)}</span>
                  <span className="muted small">共 {items.length} 个单词</span>
                  <span className="word-group-bar">
                    <span style={{ width: `${pct}%` }} />
                  </span>
                  <span className="muted small">{pct}%</span>
                  <span className="badge badge-new">新词 {isNew}</span>
                  <span className="badge badge-learn">学习中 {learning}</span>
                  <span className="badge badge-done">已掌握 {reviewed}</span>
                </button>
                {open && (
                  <>
                    <table className="table">
                      <thead>
                        <tr>
                          <th style={{ width: 30 }}></th>
                          <th>单词</th>
                          <th>中文含义</th>
                          <th>语境例句</th>
                          <th>状态</th>
                          <th>下次复习</th>
                          <th>来源</th>
                          <th></th>
                        </tr>
                      </thead>
                      <tbody>
                        {items.map((c) => (
                          <tr key={c.id}>
                            <td>
                              <input
                                type="checkbox"
                                checked={selected.has(c.id)}
                                onChange={() =>
                                  setSelected((prev) => {
                                    const next = new Set(prev);
                                    if (next.has(c.id)) next.delete(c.id);
                                    else next.add(c.id);
                                    return next;
                                  })
                                }
                              />
                            </td>
                            <td style={{ fontWeight: 600, fontFamily: "var(--serif)" }}>
                              {c.headword}
                              {c.audio_clip_key && (
                                <button
                                  className="audio-btn"
                                  title="播放原声"
                                  onClick={() =>
                                    new Audio(api.cardAudioUrl(c.id)).play().catch(() => undefined)
                                  }
                                >
                                  🔊
                                </button>
                              )}
                            </td>
                            <td>{c.meaning_zh}</td>
                            <td className="muted" style={{ maxWidth: 280 }}>
                              {c.example_en ? <BoldWord text={c.example_en} word={c.headword} /> : "—"}
                            </td>
                            <td>{stateBadge(c.state)}</td>
                            <td className="muted small">{dueLabel(c.due_at)}</td>
                            <td>
                              {c.media_id ? (
                                <Link to={`/media/${c.media_id}`} style={{ color: "var(--accent)" }}>
                                  视频
                                </Link>
                              ) : (
                                <span className="muted">—</span>
                              )}
                            </td>
                            <td style={{ textAlign: "right" }}>
                              <button
                                className="btn btn-ghost small btn-danger"
                                onClick={() => void removeCard(c)}
                              >
                                删除
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <div className="row" style={{ gap: 8, padding: "8px 10px" }}>
                      <button className="btn small" onClick={() => toggleGroup(items)}>
                        {inGroupAllSelected(items) ? "取消本组" : "全选本组"}
                      </button>
                      <Link className="btn small" to={`/review?day=${key}`}>
                        复习本组
                      </Link>
                    </div>
                  </>
                )}
              </div>
            );
          })
        )}
      </div>

      <aside className="words-side">
        <StoryPanel words={storyWords} hasToday={storyWords.length > 0 && groups[0]?.[0] === todayKey} />
        <MiniReview />
      </aside>
    </div>
  );
}
