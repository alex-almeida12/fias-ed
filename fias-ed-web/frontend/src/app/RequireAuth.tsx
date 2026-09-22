import type { ReactNode } from "react";
import { Navigate } from "react-router";
import { useAuth } from "./AuthContext";

export function RequireAuth({ children, allowPasswordChange = false }: { children: ReactNode; allowPasswordChange?: boolean }) {
  const { me, loading } = useAuth();
  if (loading) return <p className="page" role="status">Carregando…</p>;
  if (!me) return <Navigate to="/" replace />;
  if (me.must_change_password && !allowPasswordChange) return <Navigate to="/trocar-senha" replace />;
  return <>{children}</>;
}

export function RequireAdmin({ children }: { children: ReactNode }) {
  const { me } = useAuth();
  if (me?.role !== "ADMIN_LOCAL") return <Navigate to="/aulas" replace />;
  return <>{children}</>;
}
