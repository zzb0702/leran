import { FormEvent, useEffect, useState } from "react";
import { api, ProviderRow } from "../api";

function ProviderForm({
  row,
  onSave,
}: {
  row: ProviderRow;
  onSave: (body: {
    kind: string;
    provider_id: string;
    api_key?: string;
    base_url?: string;
    model?: string;
  }) => Promise<void>;
}) {
  const [providerId, setProviderId] = useState(row.provider_id);
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState(row.base_url);
  const [model, setModel] = useState(row.model);
  const [msg, setMsg] = useState("");
  const [testState, setTestState] = useState<{
    busy: boolean;
    ok?: boolean;
    message: string;
    sample: string;
  }>({ busy: false, message: "", sample: "" });

  useEffect(() => {
    setProviderId(row.provider_id);
    setBaseUrl(row.base_url);
    setModel(row.model);
    setTestState({ busy: false, message: "", sample: "" });
  }, [row]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    await onSave({
      kind: row.kind,
      provider_id: providerId,
      api_key: apiKey || undefined,
      base_url: baseUrl,
      model,
    });
    setApiKey("");
    setMsg("已保存");
    setTimeout(() => setMsg(""), 1500);
  }

  async function runTest() {
    setTestState({ busy: true, message: "测试中…", sample: "" });
    try {
      const r = await api.testProvider({
        kind: row.kind,
        provider_id: providerId,
        api_key: apiKey || undefined,
        base_url: baseUrl,
        model,
      });
      setTestState({
        busy: false,
        ok: r.ok,
        message: r.message,
        sample: r.sample,
      });
    } catch (err) {
      setTestState({
        busy: false,
        ok: false,
        message: err instanceof Error ? err.message : "测试失败",
        sample: "",
      });
    }
  }

  const kindLabel =
    row.kind === "asr"
      ? "语音识别 ASR"
      : row.kind === "translate"
        ? "翻译"
        : row.kind === "dict"
          ? "查词兜底（在线）"
          : "释义 Enrich";

  return (
    <form className="card-box" onSubmit={submit} style={{ marginBottom: 16 }}>
      <div style={{ fontWeight: 500, marginBottom: 12, color: "var(--n-900)" }}>{kindLabel}</div>
      <div className="field">
        <label>Provider</label>
        <select value={providerId} onChange={(e) => setProviderId(e.target.value)}>
          {row.kind === "dict" ? (
            <option value="baidu">baidu（百度翻译 · 官方，有免费额度）</option>
          ) : (
            <>
              <option value="mock">mock（离线演示）</option>
              <option value="openai">openai / 兼容接口</option>
              {row.kind === "asr" && (
                <option value="local-whisper">local-whisper（本机 faster-whisper）</option>
              )}
            </>
          )}
        </select>
      </div>
      {row.kind === "dict" && (
        <>
          <div className="field">
            <label>APP ID（百度翻译开放平台 → 开发者信息）</label>
            <input
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="例如 20250101001234567"
            />
          </div>
          <div className="field">
            <label>密钥 {row.has_api_key ? "（已保存，留空不变）" : ""}</label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="百度翻译密钥"
            />
          </div>
          <p className="small muted" style={{ marginTop: 4 }}>
            仅当离线 ECDICT 和有道都查不到时才调用。标准版每月 5 万字符免费（QPS=1），
            个人认证后每月 100 万；建议在百度控制台开启免费额度用量提醒。
          </p>
        </>
      )}
      {providerId === "local-whisper" && (
        <div className="field">
          <label>模型（distil / base / small / medium / large-v3 或本地路径）</label>
          <input
            value={model || "distil"}
            onChange={(e) => setModel(e.target.value)}
            placeholder="distil"
          />
        </div>
      )}
      {providerId === "openai" && (
        <>
          <div className="field">
            <label>API Key {row.has_api_key ? "（已保存，留空不变）" : ""}</label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="sk-..."
            />
          </div>
          <div className="field">
            <label>Base URL</label>
            <input
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://api.openai.com/v1"
            />
          </div>
          <div className="field">
            <label>Model</label>
            <input
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder={row.kind === "asr" ? "whisper-1" : "gpt-4o-mini"}
            />
          </div>
        </>
      )}
      <div className="row">
        <button className="btn" type="submit">
          保存
        </button>
        <button
          className="btn"
          type="button"
          disabled={testState.busy}
          onClick={runTest}
          title="用当前表单配置做一次连通性测试（不必先保存）"
        >
          {testState.busy ? "测试中…" : "测试"}
        </button>
        {msg && <span className="small muted">{msg}</span>}
      </div>
      {testState.message && (
        <div
          className="small"
          style={{
            marginTop: 10,
            color: testState.ok === false ? "var(--error)" : "var(--accent)",
          }}
        >
          {testState.ok === false ? "失败：" : "成功："}
          {testState.message}
          {testState.sample && (
            <div className="muted" style={{ marginTop: 4, color: "var(--n-500)" }}>
              示例：{testState.sample}
            </div>
          )}
        </div>
      )}
    </form>
  );
}

export default function Settings() {
  const [rows, setRows] = useState<ProviderRow[]>([]);
  const [error, setError] = useState("");

  async function load() {
    try {
      setRows(await api.providers());
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function save(body: Parameters<typeof api.saveProvider>[0]) {
    await api.saveProvider(body);
    await load();
  }

  return (
    <div>
      <h1 className="page-title">设置</h1>
      <p className="page-sub">
        配置 ASR / 翻译 / 释义。填完先点「测试」确认连通，再保存，避免看视频时才踩坑。Key 只存本机服务端。
      </p>
      {error && <p className="error-text">{error}</p>}
      {rows.map((r) => (
        <ProviderForm key={r.kind} row={r} onSave={save} />
      ))}
    </div>
  );
}
