import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, setUnauthenticatedHandler } from "../api/client";
import type { Me } from "../api/types";

type AuthState = {
  me: Me | null;
  loading: boolean;
  // Aviso para a tela de entrada (ex.: sessão expirada); some ao entrar de novo.
  aviso: string | null;
  refresh: () => Promise<void>;
  setMe: (me: Me | null) => void;
};

const AuthContext = createContext<AuthState | null>(null);

export const SESSAO_EXPIRADA = "Sua sessão terminou. Entre de novo com seu usuário e senha.";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMeState] = useState<Me | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const setMe = useCallback((next: Me | null) => {
    if (next) setAviso(null);
    setMeState(next);
  }, []);
  const refresh = useCallback(async () => {
    try {
      setMe(await api<Me>("/auth/me"));
    } catch {
      setMe(null);
    } finally {
      setLoading(false);
    }
  }, [setMe]);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  // Só com sessão aberta: um 401 significa que ela expirou (ou foi encerrada pelo administrador).
  useEffect(() => {
    if (!me) return;
    setUnauthenticatedHandler(() => {
      setMeState(null);
      setAviso(SESSAO_EXPIRADA);
    });
    return () => setUnauthenticatedHandler(null);
  }, [me]);
  return <AuthContext.Provider value={{ me, loading, aviso, refresh, setMe }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("AuthProvider ausente");
  return ctx;
}
