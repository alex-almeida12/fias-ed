import { NavLink, Outlet, useNavigate } from "react-router";
import { api } from "../api/client";
import type { Me } from "../api/types";
import { Button } from "../design/components/Button";
import { useAuth } from "./AuthContext";

export function Layout() {
  const { me, setMe } = useAuth();
  const navigate = useNavigate();
  if (!me) return null;

  async function sair() {
    await api("/auth/logout", { method: "POST" });
    setMe(null);
    navigate("/", { replace: true });
  }

  async function voltar() {
    setMe(await api<Me>("/admin/agir-como", { method: "DELETE" }));
    navigate("/admin/aulas");
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
        <Outlet />
      </main>
    </>
  );
}
