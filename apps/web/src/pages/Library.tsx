import { ChangeEvent, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, MediaItem } from "../api";

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

function fmtSize(n: number) {
  if (!n) return "—";
  if (n > 1024 * 1024 * 1024) return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`;
  if (n > 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${Math.round(n / 1024)} KB`;
}

function fmtDur(ms: number) {
  if (!ms) return "—";
  const s = Math.round(ms / 1000);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h) return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  return `${m}:${String(sec).padStart(2, "0")}`;
}

export default function Library() {
  const [items, setItems] = useState<MediaItem[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<{ pct: number; label: string } | null>(null);
  const [limits, setLimits] = useState<{ max_upload_mb: number; chunk_size_mb: number } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function refresh() {
    try {
      setItems(await api.listMedia());
      // Don't clear upload errors here — only list failures
    } catch (e) {
      // Keep list UI usable; only surface if we have no items
      setItems((prev) => {
        if (prev.length === 0) {
          setError(e instanceof Error ? e.message : "加载失败");
        }
        return prev;
      });
    }
  }

  useEffect(() => {
    refresh();
    api
      .uploadLimits()
      .then((l) => setLimits({ max_upload_mb: l.max_upload_mb, chunk_size_mb: l.chunk_size_mb }))
      .catch(() => undefined);
    const t = setInterval(() => {
      refresh();
    }, 2500);
    return () => clearInterval(t);
  }, []);

  async function onFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError("");
    setProgress({ pct: 0, label: `准备上传 ${fmtSize(file.size)}` });
    try {
      await api.uploadMedia(file, "", (pct, label) => setProgress({ pct, label }));
      await refresh();
      setTimeout(() => setProgress(null), 1200);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "上传失败";
      const sizeHint =
        file.size > 2048 * 1024 * 1024
          ? "（文件超过 2048MB 上限）"
          : file.size > 8 * 1024 * 1024
            ? `（已走分片，约 ${fmtSize(file.size)}）`
            : "";
      setError(`${msg}${sizeHint}`);
      setProgress(null);
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
        <div>
          <h1 className="page-title">媒体库</h1>
          <p className="page-sub" style={{ marginBottom: 0 }}>
            上传英语视频/音频。大文件自动分片；处理时会先抽 16k 音频再识别。
            {limits && (
              <span className="muted">
                {" "}
                上限 {limits.max_upload_mb}MB · 分片 {limits.chunk_size_mb}MB
              </span>
            )}
          </p>
        </div>
        <label className="btn btn-fill" style={{ cursor: "pointer" }}>
          {busy ? "上传中…" : "上传视频"}
          <input
            ref={fileRef}
            type="file"
            accept="video/*,audio/*,.mkv,.mov,.mp4,.webm,.mp3,.wav,.m4a"
            hidden
            onChange={onFile}
          />
        </label>
      </div>

      {progress && (
        <div className="card-box" style={{ marginBottom: 16 }}>
          <div className="row" style={{ justifyContent: "space-between", marginBottom: 6 }}>
            <span className="small">{progress.label}</span>
            <span className="muted small">{progress.pct}%</span>
          </div>
          <div style={{ height: 6, background: "var(--n-100)", borderRadius: 3 }}>
            <div
              style={{
                width: `${progress.pct}%`,
                height: "100%",
                background: "var(--accent)",
                borderRadius: 3,
                transition: "width 150ms linear",
              }}
            />
          </div>
        </div>
      )}

      {error && <p className="error-text">{error}</p>}

      {items.length === 0 ? (
        <div className="empty">
          还没有视频。拖入或点击「上传视频」。建议长片优先传音频（体积更小）。mock 模式无需
          API Key。
        </div>
      ) : (
        <div>
          {items.map((m) => (
            <div className="list-row" key={m.id}>
              <div>
                <Link to={`/media/${m.id}`} style={{ fontWeight: 500, color: "var(--n-900)" }}>
                  {m.title}
                </Link>
                <div className="muted small">
                  {fmtDur(m.duration_ms)} · {fmtSize(m.file_size)} · ASR {m.asr_provider} · 译{" "}
                  {m.translate_provider} · {m.segment_count} 句 · {m.card_count} 卡
                  {m.progress ? ` · ${m.progress}` : ""}
                </div>
                {m.error && <div className="error-text small">{m.error}</div>}
              </div>
              <div className="row">
                <span className="status">
                  <span className={`dot ${statusDot(m.status)}`} />
                  {statusLabel(m.status)}
                </span>
                {(m.status === "failed" || m.asr_provider === "mock") && (
                  <button
                    className="btn"
                    title={m.asr_provider === "mock" ? "用当前设置的真实 ASR 重新识别" : "重跑"}
                    onClick={() => {
                      if (
                        m.asr_provider === "mock" &&
                        !confirm("当前字幕是 mock 演示文案。要用设置里的 ASR（如 local-whisper）重新识别吗？长视频会较久。")
                      ) {
                        return;
                      }
                      api.reprocess(m.id).then(refresh);
                    }}
                  >
                    {m.asr_provider === "mock" ? "真实识别" : "重跑"}
                  </button>
                )}
                <button
                  className="btn btn-ghost"
                  title="重命名"
                  onClick={async () => {
                    const name = prompt("修改视频名称", m.title);
                    if (name === null) return;
                    const title = name.trim();
                    if (!title) {
                      alert("名称不能为空");
                      return;
                    }
                    try {
                      await api.renameMedia(m.id, title);
                      refresh();
                    } catch (e) {
                      alert(e instanceof Error ? e.message : "重命名失败");
                    }
                  }}
                >
                  重命名
                </button>
                <button
                  className="btn btn-ghost btn-danger"
                  onClick={() => {
                    if (confirm("删除该视频及其字幕？")) {
                      api.deleteMedia(m.id).then(refresh);
                    }
                  }}
                >
                  删除
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
