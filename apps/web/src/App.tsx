import { Link, Navigate, NavLink, Outlet, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { getToken, setToken } from "./api";
import {
  IconBook,
  IconGear,
  IconGraph,
  IconHome,
  IconLeaf,
  IconMedia,
  IconQuote,
  IconRepeat,
} from "./icons";
import Login from "./pages/Login";
import Today from "./pages/Today";
import Library from "./pages/Library";
import Workbench from "./pages/Workbench";
import Review from "./pages/Review";
import Words from "./pages/Words";
import Sentences from "./pages/Sentences";
import Graph from "./pages/Graph";
import Settings from "./pages/Settings";
import GlobalSearch from "./pages/GlobalSearch";

const NAV = [
  { to: "/", label: "今日", Icon: IconHome },
  { to: "/library", label: "媒体库", Icon: IconMedia },
  { to: "/review", label: "复习", Icon: IconRepeat },
  { to: "/words", label: "词库", Icon: IconBook },
  { to: "/sentences", label: "句库", Icon: IconQuote },
  { to: "/graph", label: "图谱", Icon: IconGraph },
  { to: "/settings", label: "设置", Icon: IconGear },
];

function Shell() {
  const nav = useNavigate();
  const loc = useLocation();
  const immersive = /^\/media\//.test(loc.pathname);
  return (
    <div className={`app-shell${immersive ? " shell-immersive" : ""}`}>
      {!immersive && (
        <aside className="sidebar">
          <div className="brand">
            Leran <IconLeaf />
          </div>
          <div className="brand-sub">Learn English from Real Videos</div>
          <div style={{ height: 18 }} />
          {NAV.map(({ to, label, Icon }) => (
            <NavLink
              key={to}
              className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
              to={to}
            >
              <span className="nav-ic">
                <Icon />
              </span>
              {label}
            </NavLink>
          ))}
          <div style={{ flex: 1 }} />
          <div className="side-quote">
            “A new word
            <br />
            is a new world.”
          </div>
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
      {immersive ? (
        <main className="main">
          <Outlet />
        </main>
      ) : (
        <div className="main-col">
          <header className="topbar">
            <GlobalSearch />
            <div style={{ flex: 1 }} />
            <Link to="/library" className="btn btn-fill topbar-upload">
              ＋ 上传视频
            </Link>
          </header>
          <main className="main">
            <Outlet />
          </main>
        </div>
      )}
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
        <Route path="/sentences" element={<Sentences />} />
        <Route path="/graph" element={<Graph />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
