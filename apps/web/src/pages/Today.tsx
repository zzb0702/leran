import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, TodayStats } from "../api";

function statusDot(status: string) {
  if (status === "ready") return "ready";
  if (status === "failed") return "failed";
  return "busy";
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    queued: "排队中",
    extracting_audio: "抽音频",
    transcribing: "识别中",
    translating: "翻译中",
    ready: "双语就绪",
    failed: "失败",
  };
  return map[status] || status;
}

export default function Today() {
  const [stats, setStats] = useState<TodayStats | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .today()
      .then(setStats)
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="error-text">{error}</p>;
  if (!stats) return <p className="muted">加载中…</p>;

  return (
    <div>
      <h1 className="page-title">今天</h1>
      <p className="page-sub">你现在该干什么？</p>

      <div className="card-box" style={{ marginBottom: 24 }}>
        <div className="muted small">待复习</div>
        <div style={{ fontSize: 40, fontWeight: 600, color: "var(--n-900)", margin: "4px 0 12px" }}>
          {stats.due_count + stats.new_count}
        </div>
        <div className="row">
          <Link className="btn btn-fill" to="/review">
            开始复习
          </Link>
          <span className="muted small">
            到期 {stats.due_count} · 新卡 {stats.new_count} · 学习中 {stats.learning_count}
          </span>
        </div>
      </div>

      <h2 style={{ fontSize: 16, margin: "0 0 8px", color: "var(--n-900)" }}>继续</h2>
      {stats.recent_media.length === 0 ? (
        <div className="empty">
          拖入一个英语视频到媒体库。我们会抽出英文、译成中文，你再决定留下哪些词。{" "}
          <Link to="/library" style={{ color: "var(--accent)" }}>
            去上传
          </Link>
        </div>
      ) : (
        <div>
          {stats.recent_media.map((m) => (
            <div className="list-row" key={m.id}>
              <div>
                <Link to={`/media/${m.id}`} style={{ color: "var(--n-900)", fontWeight: 500 }}>
                  {m.title}
                </Link>
                <div className="muted small">
                  {m.segment_count} 句 · {m.card_count} 卡
                  {m.error ? ` · ${m.error}` : ""}
                </div>
              </div>
              <div className="status">
                <span className={`dot ${statusDot(m.status)}`} />
                {statusLabel(m.status)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
