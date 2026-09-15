import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import ForceGraph2D from "react-force-graph-2d";
import { api, GraphData } from "../api";

const GROUPS = {
  roots: { title: "同根词", color: "#2f7d54" },
  family: { title: "同族词", color: "#2858c4" },
  similar: { title: "形近词", color: "#a15c00" },
  inflections: { title: "词形变化", color: "#7a766a" },
} as const;

type GNode = {
  id: string;
  word: string;
  zh: string;
  group: keyof typeof GROUPS;
  isCenter?: boolean;
  isRoot?: boolean;
  w: number;
  x?: number;
  y?: number;
};
type GLink = { source: string; target: string; color: string; dist: number };

/** center + (root → siblings) + per-group nodes; dedupe repeated words.
 *  Nodes are seeded in a radial layout so the simulation starts sane. */
function toGraph(d: GraphData): { nodes: GNode[]; links: GLink[] } {
  const nodes: GNode[] = [];
  const links: GLink[] = [];
  const seen = new Set<string>([d.word]);
  let seed = 0;

  const pos = (r: number) => {
    const a = (seed++ / 7) * Math.PI * 2;
    return { x: Math.cos(a) * r, y: Math.sin(a) * r * 0.72 };
  };

  nodes.push({
    id: d.word,
    word: d.word,
    zh: d.meaning_zh.slice(0, 26),
    group: "family",
    isCenter: true,
    w: Math.max(92, d.word.length * 13 + 36),
    x: 0,
    y: 0,
  });

  const add = (group: keyof typeof GROUPS, word: string, zh: string, label: string) => {
    if (word === d.word || word.length > 18) return;
    const w = Math.max(54, word.length * 8.6 + 26);
    if (seen.has(word)) return;
    seen.add(word);
    const p = pos(170 + (seed % 4) * 42);
    nodes.push({ id: word, word, zh, group, w, ...p });
    links.push({ source: d.word, target: word, color: GROUPS[group].color, dist: 118 });
  };

  for (const r of d.groups.roots) {
    const rid = `root:${r.root}`;
    const siblings = r.words.filter((n) => n.word !== d.word && n.word.length <= 18);
    if (r.root === d.word) {
      // The query word IS this root — hang siblings directly off the center.
      for (const n of siblings) {
        if (seen.has(n.word)) continue;
        seen.add(n.word);
        const w = Math.max(54, n.word.length * 8.6 + 26);
        const p = pos(190 + (seed % 4) * 40);
        nodes.push({ id: n.word, word: n.word, zh: n.zh, group: "roots", w, ...p });
        links.push({ source: d.word, target: n.word, color: GROUPS.roots.color, dist: 150 });
      }
      continue;
    }
    const hub = pos(105);
    nodes.push({
      id: rid,
      word: r.root,
      zh: r.meaning,
      group: "roots",
      isRoot: true,
      w: Math.max(78, r.root.length * 11 + 52),
      x: hub.x,
      y: hub.y,
    });
    links.push({ source: d.word, target: rid, color: GROUPS.roots.color, dist: 92 });
    for (const n of siblings) {
      if (seen.has(n.word)) continue;
      seen.add(n.word);
      const w = Math.max(54, n.word.length * 8.6 + 26);
      const p = pos(60);
      nodes.push({
        id: n.word,
        word: n.word,
        zh: n.zh,
        group: "roots",
        w,
        x: hub.x + p.x * 0.6,
        y: hub.y + p.y * 0.6,
      });
      links.push({ source: rid, target: n.word, color: GROUPS.roots.color, dist: 66 });
    }
  }
  for (const n of d.groups.family) add("family", n.word, n.zh, n.label);
  for (const n of d.groups.similar) add("similar", n.word, n.zh, n.label);
  for (const n of d.groups.inflections) add("inflections", n.word, n.zh, n.label);
  return { nodes, links };
}

function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

export default function Graph() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [input, setInput] = useState(searchParams.get("word") || "");
  const [data, setData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [hover, setHover] = useState<GNode | null>(null);
  const [added, setAdded] = useState<Record<string, boolean>>({});
  const [cardMsg, setCardMsg] = useState("");
  const [w, setW] = useState(860);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const fgRef = useRef<{
    zoomToFit?: (ms?: number, px?: number) => void;
    d3Force?: (
      name: string,
    ) => { strength?: (v: number) => void; distance?: (f: (l: GLink) => number) => void } | undefined;
  }>(undefined);

  async function fetchWord(word: string) {
    const t = word.trim().toLowerCase();
    if (!t) return;
    setLoading(true);
    setError("");
    setHover(null);
    try {
      setData(await api.graphWord(t));
      setSearchParams({ word: t }, { replace: true });
    } catch (e) {
      setData(null);
      setError(e instanceof Error ? e.message : "查询失败");
    } finally {
      setLoading(false);
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    void fetchWord(input);
  }

  async function addCard(word: string, zh: string, pos = "") {
    if (added[word]) return;
    try {
      await api.createCard({ headword: word, meaning_zh: zh, pos });
      setAdded((a) => ({ ...a, [word]: true }));
      setCardMsg(`已入卡：${word}`);
      setTimeout(() => setCardMsg(""), 2500);
    } catch (e) {
      setCardMsg(e instanceof Error ? e.message : "入卡失败");
      setTimeout(() => setCardMsg(""), 3000);
    }
  }

  useEffect(() => {
    const urlWord = searchParams.get("word");
    if (urlWord) void fetchWord(urlWord);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const update = () => setW(el.clientWidth - 4);
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, [data]);

  const graphData = useMemo(() => (data ? toGraph(data) : null), [data]);

  useEffect(() => {
    if (!graphData) return;
    const fg = fgRef.current;
    fg?.d3Force?.("charge")?.strength?.(-460);
    fg?.d3Force?.("link")?.distance?.((l: GLink) => l.dist);
    // Fit once the simulation has had time to settle (cooldown runs ~4s).
    const t = window.setTimeout(() => fgRef.current?.zoomToFit?.(700, 64), 1500);
    return () => window.clearTimeout(t);
  }, [graphData]);

  return (
    <div>
      <h1 className="page-title">单词图谱</h1>
      <p className="page-sub">
        一个词带出一片网：同根词（词源）、同族词（派生）、形近词（易混）、词形变化。全部离线来自
        ECDICT。拖动/滚轮缩放，点击节点切换中心词，悬停节点看释义。
      </p>

      <form className="row" style={{ marginBottom: 14 }} onSubmit={submit}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="输入一个单词，如 inspect / adapt"
          style={{
            border: "1px solid var(--n-100)",
            borderRadius: "var(--radius-s)",
            padding: "9px 12px",
            minWidth: 260,
            background: "#fff",
          }}
        />
        <button className="btn btn-fill" type="submit" disabled={loading}>
          {loading ? "构建中…" : "生成图谱"}
        </button>
        <span className="row" style={{ gap: 10 }}>
          {Object.values(GROUPS).map((g) => (
            <span key={g.title} className="small" style={{ color: g.color, fontWeight: 600 }}>
              ● {g.title}
            </span>
          ))}
        </span>
      </form>

      {error && <p className="error-text">{error}</p>}

      {data && graphData && (
        <div className="card-box graph-wrap" ref={wrapRef} style={{ padding: 10 }}>
          <div style={{ position: "relative" }}>
            <ForceGraph2D
              ref={fgRef as never}
              graphData={graphData as never}
              width={Math.max(320, w)}
              height={600}
              backgroundColor="rgba(0,0,0,0)"
              nodeId="id"
              linkColor={(l: GLink) => l.color + "66"}
              linkWidth={1.2}
              linkDirectionalParticles={0}
              nodeCanvasObjectMode={() => "replace"}
              nodeCanvasObject={(n: GNode, ctx: CanvasRenderingContext2D) => {
                if (n.x == null || n.y == null) return;
                const h = n.isCenter ? 40 : 30;
                const x = n.x;
                const y = n.y;
                ctx.shadowColor = "rgba(28,27,20,0.18)";
                ctx.shadowBlur = n.isCenter ? 12 : 6;
                ctx.shadowOffsetY = n.isCenter ? 3 : 1.5;
                roundRect(ctx, x - n.w / 2, y - h / 2, n.w, h, h / 2);
                if (n.isCenter) {
                  ctx.fillStyle = "#2f7d54";
                } else if (n.isRoot) {
                  ctx.fillStyle = "#e7f1ea";
                } else {
                  ctx.fillStyle = "#ffffff";
                }
                ctx.fill();
                ctx.shadowColor = "transparent";
                ctx.lineWidth = n.isCenter ? 0 : 1.4;
                ctx.strokeStyle = GROUPS[n.group].color + (n.isRoot ? "" : "99");
                if (!n.isCenter) ctx.stroke();

                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                if (n.isCenter) {
                  ctx.font = "700 17px Georgia, 'Songti SC', serif";
                  ctx.fillStyle = "#ffffff";
                  ctx.fillText(n.word, x, y);
                } else if (n.isRoot) {
                  ctx.font = "700 13px Inter, 'PingFang SC', sans-serif";
                  ctx.fillStyle = "#256a46";
                  ctx.fillText(`${n.word} · ${n.zh}`, x, y);
                } else {
                  ctx.font = "600 12.5px Inter, 'PingFang SC', sans-serif";
                  ctx.fillStyle = "#2b2a24";
                  ctx.fillText(n.word, x, y - 1);
                }
                if (!n.isCenter && n.zh) {
                  ctx.font = "9.5px Inter, 'PingFang SC', sans-serif";
                  ctx.fillStyle = "#9b978a";
                  const zh = n.zh.length > 16 ? n.zh.slice(0, 16) + "…" : n.zh;
                  ctx.fillText(zh, x, y + h / 2 + 9);
                }
              }}
              nodePointerAreaPaint={(n: GNode, color: string, ctx: CanvasRenderingContext2D) => {
                if (n.x == null || n.y == null) return;
                const h = n.isCenter ? 44 : 34;
                ctx.fillStyle = color;
                roundRect(ctx, n.x - n.w / 2, n.y - h / 2, n.w, h, h / 2);
                ctx.fill();
              }}
              onNodeHover={(n: GNode | null) => setHover(n ?? null)}
              onEngineStop={() => fgRef.current?.zoomToFit?.(600, 64)}
              onNodeClick={(n: GNode, event?: { shiftKey?: boolean }) => {
                if (n.isRoot) return;
                if (event?.shiftKey) {
                  void addCard(n.word, n.zh);
                  return;
                }
                setInput(n.word);
                void fetchWord(n.word);
              }}
              cooldownTime={4200}
            />
            {hover && (
              <div className="graph-tip" style={{ right: 14, top: 14, left: "auto" }}>
                <div style={{ fontWeight: 700, fontFamily: "var(--serif)" }}>
                  {hover.word}
                  <span className="small muted" style={{ marginLeft: 8 }}>
                    {GROUPS[hover.group].title}
                  </span>
                </div>
                {hover.zh && <div className="small">{hover.zh}</div>}
                {!hover.isRoot && <div className="small muted">点击切换为中心词</div>}
              </div>
            )}
          </div>
          {data.meaning_zh && (
            <>
              <p className="muted small" style={{ textAlign: "center", margin: "6px 0 2px" }}>
                <strong style={{ color: "var(--n-900)" }}>{data.word}</strong>
                {data.pos ? ` (${data.pos})` : ""} · {data.meaning_zh}
              </p>
              <div className="row" style={{ justifyContent: "center", gap: 10, marginBottom: 2 }}>
                <button
                  className={`btn small${added[data.word] ? "" : " btn-fill"}`}
                  disabled={added[data.word]}
                  title="以当前中心词建一张单词卡（附图中释义）"
                  onClick={() => addCard(data.word, data.meaning_zh, data.pos)}
                >
                  {added[data.word] ? "✓ 中心词已在词库" : "把中心词加入词库"}
                </button>
                <span className="muted small">点击节点切换中心词 · Shift+点击节点 = 直接入卡</span>
              </div>
              {cardMsg && (
                <p className="small" style={{ textAlign: "center", color: "var(--accent)", margin: "2px 0 0" }}>
                  {cardMsg}
                </p>
              )}
            </>
          )}
        </div>
      )}

      {!data && !loading && !error && (
        <div className="empty">
          输入一个单词开始探索。试试 <strong>inspect</strong>（spect 词根家族）、
          <strong>adapt</strong>（adopt/adept 形近词）、<strong>courage</strong>（courageous 同族词）。
        </div>
      )}
    </div>
  );
}
