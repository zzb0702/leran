import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, setToken } from "../api";

export default function Login() {
  const nav = useNavigate();
  const [email, setEmail] = useState("demo@leran.local");
  const [password, setPassword] = useState("demo1234");
  const [mode, setMode] = useState<"login" | "register">("login");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (mode === "register") {
        await api.register(email, password);
      }
      await api.login(email, password);
      nav("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <form className="auth-card" onSubmit={onSubmit}>
        <h1 className="page-title">WordReel</h1>
        <p className="page-sub">用真实英语视频学单词，并导出中英双语字幕。</p>
        <div className="field">
          <label>邮箱</label>
          <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
        </div>
        <div className="field">
          <label>密码</label>
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            minLength={6}
            required
          />
        </div>
        {error && <p className="error-text">{error}</p>}
        <div className="row" style={{ marginTop: 8 }}>
          <button className="btn btn-fill" disabled={busy} type="submit">
            {mode === "login" ? "登录" : "注册并登录"}
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => setMode(mode === "login" ? "register" : "login")}
          >
            {mode === "login" ? "没有账号？注册" : "已有账号？登录"}
          </button>
        </div>
      </form>
    </div>
  );
}
