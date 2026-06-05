import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { Layout } from "./components/Layout";
import { Login } from "./pages/Login";
import { Dashboard } from "./pages/Dashboard";
import { Events } from "./pages/Events";
import { Hives } from "./pages/Hives";
import { Honeypots } from "./pages/Honeypots";
import { Instances } from "./pages/Instances";
import { Jobs } from "./pages/Jobs";
import { Admin } from "./pages/Admin";
import { ReactNode } from "react";

function RequireAuth({ children, role }: { children: ReactNode; role?: string }) {
  const { user, loading, hasRole } = useAuth();
  if (loading) return <div className="centered">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (role && !hasRole(role)) return <div className="centered">403 — insufficient role</div>;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<Dashboard />} />
        <Route path="/events" element={<Events />} />
        <Route path="/hives" element={<Hives />} />
        <Route path="/honeypots" element={<Honeypots />} />
        <Route path="/instances" element={<Instances />} />
        <Route path="/jobs" element={<Jobs />} />
        <Route
          path="/admin"
          element={
            <RequireAuth role="admin">
              <Admin />
            </RequireAuth>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
