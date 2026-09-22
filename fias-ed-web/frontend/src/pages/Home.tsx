import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router";
import { api, ApiError } from "../api/client";
import type { Me } from "../api/types";
import { useAuth } from "../app/AuthContext";
import { Banner } from "../design/components/Banner";
import { Button } from "../design/components/Button";
import { TextField } from "../design/components/Field";

export function Home() {
  const { me, loading, aviso, setMe } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!loading && me) return <Navigate to={me.must_change_password ? "/trocar-senha" : "/aulas"} replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const next = await api<Me>("/auth/login", { method: "POST", json: { username, password } });
      setMe(next);
      navigate(next.must_change_password ? "/trocar-senha" : "/aulas", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível entrar. Tente novamente.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="home">
      <section>
        <p className="home__brand">FIAS-ED</p>
        <h1 className="home__title">Grave sua aula.<br />Melhore sua prática docente.</h1>
        <p>Envie o áudio de uma aula e conheça melhor os padrões de interação que acontecem em sala.</p>
      </section>
      <section className="home__login" aria-labelledby="entrar-titulo">
        <h2 id="entrar-titulo">Entrar</h2>
        {aviso && <Banner kind="info">{aviso}</Banner>}
        <form onSubmit={onSubmit} noValidate>
          <TextField label="Usuário" name="username" autoComplete="username" value={username}
            onChange={(e) => setUsername(e.target.value)} required />
          <TextField label="Senha" name="password" type="password" autoComplete="current-password" value={password}
            onChange={(e) => setPassword(e.target.value)} required />
          {error && <Banner kind="error">{error}</Banner>}
          <Button type="submit" disabled={busy}>{busy ? "Entrando…" : "Entrar"}</Button>
        </form>
      </section>
    </main>
  );
}
