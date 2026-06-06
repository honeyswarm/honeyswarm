import { createContext, useContext, useEffect, useMemo, useState, ReactNode } from "react";
import { api, tokens } from "../api/client";

export interface User {
  id: string;
  email: string;
  name: string | null;
  roles: string[];
  active: boolean;
}

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  hasRole: (role: string) => boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // On load, if we hold a token try to resolve the current user.
  useEffect(() => {
    let active = true;
    (async () => {
      if (tokens.access || tokens.refresh) {
        try {
          const me = await api<User>("/auth/me");
          if (active) setUser(me);
        } catch {
          tokens.clear();
        }
      }
      if (active) setLoading(false);
    })();
    return () => {
      active = false;
    };
  }, []);

  // Keep a Dashboards SSO cookie fresh whenever we hold an active session, so
  // Caddy's /dashboards forward_auth gate passes without a second login (e.g. a
  // bookmarked /dashboards URL). Best-effort.
  useEffect(() => {
    if (!user) return;
    api("/auth/dashboards-session", { method: "POST" }).catch(() => {});
  }, [user]);

  async function login(email: string, password: string) {
    const data = await api<{ access_token: string; refresh_token: string; user: User }>(
      "/auth/login",
      { method: "POST", body: JSON.stringify({ email, password }) },
    );
    tokens.set(data.access_token, data.refresh_token);
    setUser(data.user);
  }

  function logout() {
    tokens.clear();
    setUser(null);
  }

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      login,
      logout,
      hasRole: (role: string) => !!user?.roles.includes(role),
    }),
    [user, loading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
