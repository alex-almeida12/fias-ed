import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { api, ApiError } from "../api/client";
import type { Me } from "../api/types";
import { useAuth } from "../app/AuthContext";
import { Banner } from "../design/components/Banner";
import { Button } from "../design/components/Button";
import { TextField } from "../design/components/Field";

export function TrocarSenha() {
  const { me, setMe } = useAuth();
  const navigate = useNavigate();
  const [atual, setAtual] = useState("");
  const [nova, setNova] = useState("");
  const [repetida, setRepetida] = useState("");
  const [fieldError, setFieldError] = useState<string | undefined>();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (nova.length < 12) return setFieldError("A senha precisa ter pelo menos 12 caracteres.");
    if (nova !== repetida) return setFieldError("As duas senhas precisam ser iguais.");
    setFieldError(undefined);
    setBusy(true);
    try {
      setMe(await api<Me>("/auth/password", { method: "POST", json: { current_password: atual, new_password: nova } }));
      navigate("/aulas", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível trocar a senha.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page">
      <h1>Troque sua senha</h1>
      {me?.must_change_password && <p>Por segurança, crie uma senha só sua antes de continuar.</p>}
      <form onSubmit={onSubmit} noValidate>
        <TextField label="Senha atual" type="password" autoComplete="current-password" value={atual}
          onChange={(e) => setAtual(e.target.value)} required />
        <TextField label="Nova senha" type="password" autoComplete="new-password" value={nova}
          onChange={(e) => setNova(e.target.value)} error={fieldError} required />
        <TextField label="Repita a nova senha" type="password" autoComplete="new-password" value={repetida}
          onChange={(e) => setRepetida(e.target.value)} required />
        {error && <Banner kind="error">{error}</Banner>}
        <Button type="submit" disabled={busy}>Salvar nova senha</Button>
      </form>
    </main>
  );
}
