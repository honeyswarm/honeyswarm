import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { api } from "../api/client";

const NAV = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/events", label: "Events" },
  { to: "/hives", label: "Hives" },
  { to: "/honeypots", label: "Honeypots" },
  { to: "/instances", label: "Instances" },
  { to: "/jobs", label: "Jobs" },
];

export function Layout() {
  const { user, logout, hasRole } = useAuth();

  // OpenSearch Dashboards lives outside the SPA at /dashboards. Mint a fresh
  // SSO cookie, then open it (new tab). forward_auth bounces to /login if the
  // cookie is somehow missing.
  const openDashboards = async () => {
    try {
      await api("/auth/dashboards-session", { method: "POST" });
    } catch {
      /* best-effort */
    }
    window.open("/dashboards/", "_blank", "noopener");
  };

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <img src="/honeyswarm.png" alt="Honeyswarm" />
          Honeyswarm
        </div>
        <nav>
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => (isActive ? "active" : "")}>
              {n.label}
            </NavLink>
          ))}
          {hasRole("admin") && (
            <NavLink to="/admin" className={({ isActive }) => (isActive ? "active" : "")}>
              Admin
            </NavLink>
          )}
          <a
            href="/dashboards/"
            onClick={(e) => {
              e.preventDefault();
              openDashboards();
            }}
          >
            Dashboards ↗
          </a>
        </nav>
        <div className="sidebar-footer">
          <div className="user">{user?.email}</div>
          <button className="link" onClick={logout}>
            Log out
          </button>
        </div>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
