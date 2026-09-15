import { Navigate, NavLink, Outlet, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { getToken, setToken } from "./api";
import Login from "./pages/Login";
import Today from "./pages/Today";
import Library from "./pages/Library";
import Workbench from "./pages/Workbench";
import Review from "./pages/Review";
import Words from "./pages/Words";
import Graph from "./pages/Graph";
import Settings from "./pages/Settings";

function Shell() {
  const nav = useNavigate();
  const loc = useLocation();
  const immersive = /^\/media\//.test(loc.pathname);
  return (
    <div className={`app-shell${immersive ? " shell-immersive" : ""}`}>
      {!immersive && (
        <aside className="sidebar">
          <div className="brand">Leran</div>
          <div className="brand-sub">视频词汇笔记</div>
          <div style={{ height: 10 }} />
          <NavLink className={({ isActive }) => `nav-link${isActive ? " active" : ""}`} to="/">
            今日
          </NavLink>
          <NavLink className={({ isActive }) => `nav-link${isActive ? " active" : ""}`} to="/library">
            媒体库
          </NavLink>
          <NavLink className={({ isActive }) => `nav-link${isActive ? " active" : ""}`} to="/review">
            复习
          </NavLink>
          <NavLink className={({ isActive }) => `nav-link${isActive ? " active" : ""}`} to="/words">
            词库
          </NavLink>
          <NavLink className={({ isActive }) => `nav-link${isActive ? " active" : ""}`} to="/graph">
            图谱
          </NavLink>
          <NavLink className={({ isActive }) => `nav-link${isActive ? " active" : ""}`} to="/settings">
            设置
          </NavLink>
          <div style={{ flex: 1 }} />
          <button
            className="btn btn-ghost"
            onClick={() => {
              setToken(null);
              nav("/login");
            }}
          >
            退出
          </button>
        </aside>
      )}
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}

function RequireAuth() {
  if (!getToken()) return <Navigate to="/login" replace />;
  return <Shell />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<RequireAuth />}>
        <Route path="/" element={<Today />} />
        <Route path="/library" element={<Library />} />
        <Route path="/media/:id" element={<Workbench />} />
        <Route path="/review" element={<Review />} />
        <Route path="/words" element={<Words />} />
        <Route path="/graph" element={<Graph />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
