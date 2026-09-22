import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router";
import { api, ApiError } from "../api/client";
import type { Me } from "../api/types";
import { Banner } from "../design/components/Banner";
import { Button } from "../design/components/Button";
import { useAuth } from "./AuthContext";

export function Layout() {
  const { me, setMe } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  if (!me) return null;

  // Ruling P15: sair/voltar não devem falhar em silêncio.
  async function sair() {
    setError(null);
    try {
      await api("/auth/logout", { method: "POST" });
      setMe(null);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível sair. Tente novamente.");
    }
  }

  async function voltar() {
    setError(null);
    try {
      setMe(await api<Me>("/admin/agir-como", { method: "DELETE" }));
      navigate("/admin/aulas");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível voltar à sua conta. Tente novamente.");
    }
  }

  return (
    <>
      <header className="topbar">
        <NavLink to="/aulas" className="topbar__brand">FIAS-ED</NavLink>
        <nav className="topbar__nav" aria-label="Navegação principal">
          <NavLink to="/aulas" end>Minhas aulas</NavLink>
          {me.role === "ADMIN_LOCAL" && (
            <>
              <NavLink to="/admin/aulas">Aulas dos professores</NavLink>
              <NavLink to="/admin/contas">Contas</NavLink>
              <NavLink to="/admin/escolas">Escolas</NavLink>
            </>
          )}
        </nav>
        <span>{me.display_name}</span>
        <Button variant="tertiary" onClick={sair}>Sair</Button>
      </header>
      {me.acting_as && (
        <div className="acting-banner" role="status">
          <span>Você está agindo como: {me.acting_as.display_name}</span>
          <Button variant="secondary" onClick={voltar}>Voltar à minha conta</Button>
        </div>
      )}
      <main className="page">
        {error && <Banner kind="error">{error}</Banner>}
        <Outlet />
      </main>
    </>
  );
}
