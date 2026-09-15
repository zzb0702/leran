import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, MediaItem, TodayStats } from "../api";
import { IconArrow, IconChart, IconClock, IconMoon, IconPlay, IconQuote, IconSun } from "../icons";

function statusLabel(status: string, progress: string) {
  const map: Record<string, string> = {
    queued: "排队中",
    extracting_audio: "抽音频",
    transcribing: "识别中",
    translating: "翻译中",
    ready: "已就绪",
    failed: "失败",
  };
  return map[status] || progress || status;
}

function greeting() {
  const h = new Date().getHours();
  if (h < 6) return { text: "夜深了", Icon: IconMoon };
  if (h < 12) return { text: "早上好！", Icon: IconSun };
  if (h < 18) return { text: "下午好！", Icon: IconSun };
  return { text: "晚上好！", Icon: IconMoon };
}

function weekdayOf(date: string, index: number, total: number): string {
  if (index === total - 1) return "今天";
  const names = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
  return names[new Date(`${date}T00:00:00`).getDay()];
}

function ProgressRing({ done, total }: { done: number; total: number }) {
  const pct = total > 0 ? Math.min(1, done / total) : 0;
  const r = 86;
  const c = 2 * Math.PI * r;
  return (
    <svg width={210} height={210} viewBox="0 0 210 210">
      <circle cx={105} cy={105} r={r} fill="none" stroke="var(--n-100)" strokeWidth={14} />
      <circle
        cx={105}
        cy={105}
        r={r}
        fill="none"
        stroke="var(--accent)"
        strokeWidth={14}
        strokeLinecap="round"
        strokeDasharray={`${c * pct} ${c}`}
        transform="rotate(-90 105 105)"
        style={{ transition: "stroke-dasharray 0.8s var(--ease)" }}
      />
      <text
        x={105}
        y={96}
        textAnchor="middle"
        fontSize={40}
        fontWeight={700}
        fill="var(--n-900)"
        fontFamily="var(--serif)"
      >
        {done}
      </text>
      <text x={105} y={122} textAnchor="middle" fontSize={15} fill="var(--n-500)">
        / {total} 今日已完成
      </text>
    </svg>
  );
}

function WeekBars({
  week,
}: {
  week: { date: string; new_words: number; reviews: number; minutes: number }[];
}) {
  const max = Math.max(1, ...week.map((d) => Math.max(d.reviews, d.new_words)));
  return (
    <div className="bars">
      {week.map((d, i) => {
        const last = i === week.length - 1;
        const hR = Math.round((d.reviews / max) * 86);
        const hN = Math.round((d.new_words / max) * 86);
        return (
          <div key={d.date} className="bar-col">
            <div className="bar-stack">
              {d.reviews > 0 && (
                <div
                  className="bar"
                  style={{ height: Math.max(4, hR) }}
                  title={`复习 ${d.reviews}`}
                />
              )}
              {d.new_words > 0 && (
                <div
                  className="bar bar-new"
                  style={{ height: Math.max(4, hN) }}
                  title={`新学 ${d.new_words}`}
                />
              )}
              {d.reviews === 0 && d.new_words === 0 && <div className="bar bar-zero" />}
              {last && <span className="bar-flag">今天</span>}
            </div>
            <span className={`bar-label${last ? " bar-label-today" : ""}`}>{weekdayOf(d.date, i, week.length)}</span>
          </div>
        );
      })}
    </div>
  );
}

function fmtDur(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const ss = s % 60;
  return h > 0
    ? `${h}:${String(m).padStart(2, "0")}:${String(ss).padStart(2, "0")}`
    : `${m}:${String(ss).padStart(2, "0")}`;
}

function MediaCard({ m }: { m: MediaItem }) {
  const ready = m.status === "ready";
  return (
    <div className="media-card">
      <Link to={`/media/${m.id}`} className="media-thumb">
        <img src={api.mediaThumbUrl(m.id)} alt="" loading="lazy" />
        {m.duration_ms > 0 && <span className="thumb-badge">{fmtDur(m.duration_ms)}</span>}
        {!ready && <span className="media-thumb-fallback">{(m.progress ?? "…").slice(0, 18)}</span>}
      </Link>
      <div className="media-card-main">
        <Link to={`/media/${m.id}`} className="media-card-title">
          {m.title}
        </Link>
        <div className="muted small">
          {m.segment_count} 句字幕 · {m.card_count} 个单词
        </div>
        <div className="row" style={{ gap: 6, marginTop: 8 }}>
          <span className={`badge ${ready ? "badge-done" : "badge-learn"}`}>
            {ready ? "✓ " : "◌ "}
            {statusLabel(m.status, m.progress ?? "")}
          </span>
          <span className="badge badge-new">中英双语字幕</span>
        </div>
      </div>
      <Link className="btn small" to={`/media/${m.id}`}>
        {ready ? (
          <>
            <IconPlay /> 继续学习
          </>
        ) : (
          <>
            查看进度 <IconArrow />
          </>
        )}
      </Link>
    </div>
  );
}

export default function Today() {
  const [stats, setStats] = useState<TodayStats | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    document.title = "Leran — 今日";
    api
      .today()
      .then(setStats)
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="error-text">{error}</p>;
  if (!stats) return <p className="muted">加载中…</p>;

  const g = greeting();
  const remaining = stats.due_count + stats.new_count;
  const total = remaining + stats.reviews_today;
  const estMin = Math.max(1, Math.round((remaining * 8) / 60));
  const weekNew = stats.week.reduce((a, d) => a + d.new_words, 0);
  const weekReviews = stats.week.reduce((a, d) => a + d.reviews, 0);
  const weekMin = stats.week.reduce((a, d) => a + d.minutes, 0);

  return (
    <div>
      <div className="greet-row">
        <g.Icon />
        <div>
          <h1 className="page-title" style={{ marginBottom: 2 }}>
            {g.text}
          </h1>
          <p className="page-sub" style={{ margin: 0 }}>
            每天一点真实的英语，让世界听得更清楚。
          </p>
        </div>
      </div>

      <div className="today-grid">
        <div className="card-box review-card">
          <div className="review-ring">
            <ProgressRing done={stats.reviews_today} total={total} />
          </div>
          <div className="review-card-main">
            <div className="row" style={{ gap: 8, marginBottom: 10 }}>
              <IconClock />
              <span style={{ fontWeight: 600, fontSize: 16, color: "var(--n-900)" }}>今日复习</span>
            </div>
            <div className="review-stats">
              <div className="review-stat">
                <div className="review-stat-num">{remaining}</div>
                <div className="muted small">待复习单词</div>
              </div>
              <div className="review-stat-div" />
              <div className="review-stat">
                <div className="review-stat-num">
                  {stats.reviews_today} / {total}
                </div>
                <div className="muted small">今日已完成</div>
              </div>
              <div className="review-stat-div" />
              <div className="review-stat">
                <div className="review-stat-num">
                  约 <span style={{ fontSize: 26 }}>{estMin}</span> 分钟
                </div>
                <div className="muted small">预计用时</div>
              </div>
            </div>
            {remaining > 0 || stats.reviews_today > 0 ? (
              <Link className="btn btn-fill review-cta" to="/review">
                <IconPlay /> 开始复习 <IconArrow />
              </Link>
            ) : (
              <Link className="btn review-cta" to="/library">
                今天没有待复习的词，去媒体库收新词
              </Link>
            )}
            <div className="muted small" style={{ marginTop: 12 }}>
              基于你的视频和遗忘曲线，智能推荐需要复习的单词
            </div>
          </div>
        </div>

        <div className="card-box week-card">
          <div className="row" style={{ justifyContent: "space-between", marginBottom: 14 }}>
            <div className="row" style={{ gap: 8 }}>
              <IconChart />
              <span style={{ fontWeight: 600, fontSize: 16, color: "var(--n-900)" }}>本周学习</span>
            </div>
            <Link to="/words" className="small week-more">
              查看词库 →
            </Link>
          </div>
          <WeekBars week={stats.week} />
          <div className="week-stats">
            <div>
              <div className="review-stat-num" style={{ fontSize: 22 }}>{weekNew}</div>
              <div className="muted small">新学单词</div>
            </div>
            <div>
              <div className="review-stat-num" style={{ fontSize: 22 }}>{weekReviews}</div>
              <div className="muted small">复习单词</div>
            </div>
            <div>
              <div className="review-stat-num" style={{ fontSize: 22 }}>
                {weekMin.toFixed(1)}
              </div>
              <div className="muted small">学习分钟</div>
            </div>
          </div>
        </div>
      </div>

      <div className="today-grid-lower">
        <div>
          <div className="row" style={{ justifyContent: "space-between", margin: "4px 0 12px" }}>
            <div className="row" style={{ gap: 8 }}>
              <IconClock />
              <h2 className="section-title">继续学习</h2>
            </div>
            <Link to="/library" className="small week-more">
              全部媒体 →
            </Link>
          </div>
          {stats.recent_media.length === 0 ? (
            <div className="empty">
              拖入一个英语视频到媒体库。我们会抽出英文、译成中文，你再决定留下哪些词。{" "}
              <Link to="/library" style={{ color: "var(--accent)" }}>
                去上传
              </Link>
            </div>
          ) : (
            <div className="stack">
              {stats.recent_media.map((m) => (
                <MediaCard key={m.id} m={m} />
              ))}
            </div>
          )}
        </div>

        <div>
          <div className="row" style={{ justifyContent: "space-between", margin: "4px 0 12px" }}>
            <div className="row" style={{ gap: 8 }}>
              <IconClock />
              <h2 className="section-title">最近添加</h2>
            </div>
            <Link to="/library" className="small week-more">
              全部 →
            </Link>
          </div>
          <div className="card-box recent-list">
            {stats.recent_media.slice(0, 4).map((m) => (
              <Link key={m.id} to={`/media/${m.id}`} className="recent-item">
                <span className="recent-thumb">
                  <img src={api.mediaThumbUrl(m.id)} alt="" loading="lazy" />
                  {m.duration_ms > 0 && <span className="thumb-badge">{fmtDur(m.duration_ms)}</span>}
                </span>
                <div>
                  <div className="recent-title">{m.title}</div>
                  <div className="muted small">
                    {new Date(m.updated_at.replace("Z", "")).toLocaleDateString()}
                  </div>
                </div>
              </Link>
            ))}
          </div>
          <div className="card-box quote-card">
            <IconQuote />
            <div className="quote-text">Learning never exhausts the mind.</div>
            <div className="muted small">— Leonardo da Vinci</div>
          </div>
        </div>
      </div>
    </div>
  );
}
