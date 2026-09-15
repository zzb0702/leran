import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, Card, Story } from "../api";
import { dayKeyLabel, localDayKey, parseCreated } from "../dates";

/** Render **bold** markdown spans produced by the story prompt. */
function BoldText({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <>
      {parts.map((p, i) =>
        p.startsWith("**") && p.endsWith("**") && p.length > 4 ? (
          <strong key={i}>{p.slice(2, -2)}</strong>
        ) : (
          <span key={i}>{p}</span>
        ),
      )}
    </>
  );
}

/** Story content: English part above a === line, Chinese translation below. */
function StoryBody({ content }: { content: string }) {
  const idx = content.search(/^===\s*$/m);
  const en = (idx >= 0 ? content.slice(0, idx) : content).trim();
  const zh = idx >= 0 ? content.slice(idx).replace(/^===\s*$/m, "").trim() : "";
  return (
    <div>
      <p style={{ lineHeight: 1.7, margin: "6px 0" }}>
        <BoldText text={en} />
      </p>
      {zh && (
        <p
          className="muted"
          style={{
            lineHeight: 1.7,
            margin: "6px 0 0",
            borderTop: "1px dashed var(--n-100)",
            paddingTop: 8,
          }}
        >
          {zh}
        </p>
      )}
    </div>
  );
}

function CardTable({
  cards,
  onDelete,
  selected,
  onToggle,
}: {
  cards: Card[];
  onDelete: (c: Card) => void;
  selected: Set<number>;
  onToggle: (id: number) => void;
}) {
  return (
    <table className="table">
      <thead>
        <tr>
          <th style={{ width: 30 }}></th>
          <th>词</th>
          <th>释义</th>
          <th>原句</th>
          <th>状态</th>
          <th>来源</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {cards.map((c) => (
          <tr key={c.id}>
            <td>
              <input
                type="checkbox"
                checked={selected.has(c.id)}
                onChange={() => onToggle(c.id)}
              />
            </td>
            <td style={{ fontWeight: 500, fontFamily: "var(--serif)" }}>{c.headword}</td>
            <td>{c.meaning_zh}</td>
            <td className="muted" style={{ maxWidth: 320 }}>
              {c.example_en}
            </td>
            <td className="muted small">{c.state}</td>
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
                title="删除这张卡"
                onClick={() => onDelete(c)}
              >
                删除
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function Words() {
  const [cards, setCards] = useState<Card[]>([]);
  const [stories, setStories] = useState<Story[]>([]);
  const [openDays, setOpenDays] = useState<Record<string, boolean>>({});
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [genBusy, setGenBusy] = useState<string | null>(null);
  const [storyMsg, setStoryMsg] = useState<Record<string, string>>({});
  const [q, setQ] = useState("");
  const [error, setError] = useState("");

  async function load(query = q) {
    try {
      setCards(await api.listCards(query));
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    }
  }

  useEffect(() => {
    load();
    api
      .stories()
      .then(setStories)
      .catch(() => undefined);
  }, []);

  async function generate(day: string, words: string[]) {
    setGenBusy(day);
    setStoryMsg((m) => ({ ...m, [day]: "" }));
    try {
      const s = await api.generateStory(day, words);
      setStories((prev) => [s, ...prev]);
    } catch (e) {
      setStoryMsg((m) => ({
        ...m,
        [day]: e instanceof Error ? e.message : "生成失败",
      }));
    } finally {
      setGenBusy(null);
    }
  }

  async function removeCard(c: Card) {
    if (!window.confirm(`删除「${c.headword}」？该词的复习进度和音频切片引用会一并移除。`)) return;
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

  function toggleCard(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleGroup(items: Card[]) {
    const ids = items.map((c) => c.id);
    const allIn = ids.every((id) => selected.has(id));
    setSelected((prev) => {
      const next = new Set(prev);
      for (const id of ids) {
        if (allIn) next.delete(id);
        else next.add(id);
      }
      return next;
    });
  }

  async function removeSelected() {
    const ids = [...selected];
    if (ids.length === 0) return;
    if (!window.confirm(`批量删除选中的 ${ids.length} 张卡？复习进度会一并移除，不可恢复。`)) return;
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

  const groups = useMemo(() => {
    const sorted = [...cards].sort(
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
  }, [cards]);

  return (
    <div>
      <h1 className="page-title">词库</h1>
      <p className="page-sub">从视频语境入卡的词，按入卡日期分组。可按词头筛选，可导出 Anki / CSV。</p>

      <div className="row" style={{ marginBottom: 16, flexWrap: "wrap" }}>
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

      <div className="row" style={{ marginBottom: 16 }}>
        <input
          placeholder="搜索 headword"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void load();
          }}
          style={{
            border: "1px solid var(--n-100)",
            borderRadius: 6,
            padding: "8px 10px",
            minWidth: 220,
          }}
        />
        <button className="btn" onClick={() => load()}>
          搜索
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
        groups.map(([key, items]) => {
          const isNew = items.filter((c) => c.state === "new").length;
          const learning = items.filter(
            (c) => c.state === "learning" || c.state === "relearning",
          ).length;
          const reviewed = items.filter((c) => c.state === "review").length;
          const dayStories = stories.filter((s) => s.day === key);
          const busy = genBusy === key;
          return (
            <div key={key} style={{ marginBottom: 24 }}>
              <div className="row" style={{ justifyContent: "space-between", marginBottom: 6 }}>
                <div className="row" style={{ gap: 10 }}>
                  <span style={{ fontWeight: 600, color: "var(--n-900)" }}>
                    {dayKeyLabel(key)}
                  </span>
                  <span className="muted small">{items.length} 词</span>
                  {isNew > 0 && <span className="badge badge-new">新词 {isNew}</span>}
                  {learning > 0 && <span className="badge badge-learn">学习中 {learning}</span>}
                  {reviewed > 0 && <span className="badge badge-done">已复习 {reviewed}</span>}
                </div>
                <div className="row" style={{ gap: 8 }}>
                  <button
                    className="btn small"
                    onClick={() => toggleGroup(items)}
                    title="勾选/取消本组全部"
                  >
                    {items.every((c) => selected.has(c.id)) ? "取消本组" : "全选本组"}
                  </button>
                  <button
                    className="btn small"
                    onClick={() => setOpenDays((o) => ({ ...o, [key]: !o[key] }))}
                  >
                    {openDays[key] ? "收起作文" : `AI 小作文${dayStories.length ? ` (${dayStories.length})` : ""}`}
                  </button>
                  <Link className="btn small" to={`/review?day=${key}`}>
                    复习本组
                  </Link>
                </div>
              </div>
              <CardTable
                cards={items}
                onDelete={removeCard}
                selected={selected}
                onToggle={toggleCard}
              />
              {openDays[key] && (
                <div className="card-box" style={{ marginTop: 10 }}>
                  <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
                    <span style={{ fontWeight: 500 }}>
                      AI 小作文 · 用这 {items.length} 个词写的短文
                    </span>
                    <button
                      className="btn small"
                      disabled={busy}
                      onClick={() => generate(key, items.map((c) => c.headword))}
                    >
                      {busy ? "写作中…（约 10–30 秒）" : dayStories.length ? "再写一篇" : "生成小作文"}
                    </button>
                  </div>
                  {storyMsg[key] && <p className="error-text small">{storyMsg[key]}</p>}
                  {dayStories.length === 0 && !busy && (
                    <p className="muted small">
                      还没有这一天的小作文。生成后 LLM 会把当天新词串成一篇英文短文（目标词加粗），
                      并附中文翻译，帮助在语境中记住它们。
                    </p>
                  )}
                  {dayStories.map((s) => (
                    <div
                      key={s.id}
                      style={{ borderTop: "1px solid var(--n-100)", padding: "10px 0" }}
                    >
                      <div className="row" style={{ justifyContent: "space-between" }}>
                        <span className="muted small">
                          {parseCreated(s.created_at).toLocaleString()} · 覆盖 {s.words.length} 词
                        </span>
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
                      <StoryBody content={s.content} />
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })
      )}
    </div>
  );
}
