import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, Card } from "../api";
import { dayKeyLabel, localDayKey, parseCreated } from "../dates";

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
  if (s === "new") return <span className="badge badge-new">新句</span>;
  if (s === "learning" || s === "relearning") return <span className="badge badge-learn">学习中</span>;
  return <span className="badge badge-done">已掌握</span>;
}

type StatusTab = "all" | "new" | "learning" | "review";

const STATUS_TABS: { id: StatusTab; label: string }[] = [
  { id: "all", label: "全部" },
  { id: "new", label: "新句" },
  { id: "learning", label: "学习中" },
  { id: "review", label: "已掌握" },
];

export default function Sentences() {
  const [searchParams] = useSearchParams();
  const [cards, setCards] = useState<Card[]>([]);
  const [tab, setTab] = useState<StatusTab>("all");
  const [q, setQ] = useState(searchParams.get("q") || "");
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({});

  async function load(query = q) {
    try {
      setCards(await api.listCards(query, "sentence"));
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
    const preview = c.headword.length > 48 ? `${c.headword.slice(0, 48)}…` : c.headword;
    if (!window.confirm(`删除收藏「${preview}」？复习进度会一并移除。`)) return;
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
    if (!window.confirm(`批量删除选中的 ${ids.length} 句？不可恢复。`)) return;
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
    if (failed.length > 0) setError(`${failed.length} 句删除失败，已保留勾选`);
  }

  return (
    <div className="words-page">
      <div className="words-main">
        <h1 className="page-title">句库</h1>
        <p className="page-sub">
          看视频时喜欢的整句。收藏后可 SRS 复习、听原声、跳回视频时间点。
        </p>

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
          <Link to="/words" className="words-tab words-tab-link">
            词库 →
          </Link>
        </div>

        <div className="row" style={{ marginBottom: 16, flexWrap: "wrap", gap: 8 }}>
          <input
            placeholder="搜索句子或中文…"
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
          <Link className="btn" to="/review">
            去复习
          </Link>
        </div>

        {error && <p className="error-text">{error}</p>}

        {selected.size > 0 && (
          <div className="row" style={{ marginBottom: 12, gap: 8 }}>
            <span className="small" style={{ fontWeight: 600 }}>
              已选 {selected.size} 句
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
          <div className="empty">
            还没有收藏句子。打开一个视频，在字幕工作台点「收藏本句」或按 <kbd>S</kbd>。
          </div>
        ) : (
          groups.map(([key, items], gi) => {
            const open = openGroups[key] ?? gi === 0;
            const isNew = items.filter((c) => c.state === "new").length;
            const learning = items.filter(
              (c) => c.state === "learning" || c.state === "relearning",
            ).length;
            const reviewed = items.filter((c) => c.state === "review").length;
            const pct =
              items.length > 0 ? Math.round(((learning + reviewed) / items.length) * 100) : 0;
            return (
              <div key={key} className="word-group">
                <button
                  className="word-group-head"
                  onClick={() => setOpenGroups((o) => ({ ...o, [key]: !o[key] }))}
                >
                  <span className="word-group-caret">{open ? "▾" : "▸"}</span>
                  <span className="word-group-day">{dayKeyLabel(key)}</span>
                  <span className="muted small">共 {items.length} 句</span>
                  <span className="word-group-bar">
                    <span style={{ width: `${pct}%` }} />
                  </span>
                  <span className="muted small">{pct}%</span>
                  <span className="badge badge-new">新句 {isNew}</span>
                  <span className="badge badge-learn">学习中 {learning}</span>
                  <span className="badge badge-done">已掌握 {reviewed}</span>
                </button>
                {open && (
                  <>
                    <table className="table">
                      <thead>
                        <tr>
                          <th style={{ width: 30 }}></th>
                          <th>英文句子</th>
                          <th>中文</th>
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
                            <td
                              style={{
                                fontWeight: 600,
                                fontFamily: "var(--serif)",
                                maxWidth: 360,
                              }}
                            >
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
                            <td style={{ maxWidth: 240 }} className="muted">
                              {c.meaning_zh || "—"}
                            </td>
                            <td>{stateBadge(c.state)}</td>
                            <td className="muted small">{dueLabel(c.due_at)}</td>
                            <td>
                              {c.media_id != null ? (
                                <Link
                                  to={`/media/${c.media_id}?t=${c.t_ms}`}
                                  style={{ color: "var(--accent)" }}
                                >
                                  跳回视频
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
    </div>
  );
}
