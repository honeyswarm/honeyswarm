import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

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
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <img src="/honey.png" alt="Honeyswarm" />
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
