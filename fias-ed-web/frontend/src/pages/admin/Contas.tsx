import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../../api/client";
import type { Conta, Role } from "../../api/types";
import { Banner } from "../../design/components/Banner";
import { Button } from "../../design/components/Button";
import { Dialog } from "../../design/components/Dialog";
import { SelectField, TextField } from "../../design/components/Field";

export function Contas() {
  const [contas, setContas] = useState<Conta[]>([]);
  const [form, setForm] = useState({ username: "", display_name: "", role: "PROFESSOR" as Role });
  const [senha, setSenha] = useState<{ nome: string; valor: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [excluindo, setExcluindo] = useState<Conta | null>(null);
  const [confirmacao, setConfirmacao] = useState("");

  // Ruling P15: carregamento não deve falhar em silêncio; limpa erro anterior antes de tentar
  // de novo, para um recarregamento bem-sucedido apagar o aviso de uma falha anterior.
  const carregar = useCallback(async () => {
    setError(null);
    try {
      setContas(await api<Conta[]>("/admin/contas"));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível carregar as contas.");
    }
  }, []);
  useEffect(() => {
    void carregar();
  }, [carregar]);

  async function acao(fn: () => Promise<unknown>) {
    setError(null);
    try {
      await fn();
      await carregar();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível concluir a ação.");
    }
  }

  async function criar(e: FormEvent) {
    e.preventDefault();
    await acao(async () => {
      const r = await api<{ conta: Conta; senha_provisoria: string }>("/admin/contas", { method: "POST", json: form });
      setSenha({ nome: r.conta.display_name, valor: r.senha_provisoria });
      setForm({ username: "", display_name: "", role: "PROFESSOR" });
    });
  }

  async function redefinir(c: Conta) {
    await acao(async () => {
      const r = await api<{ senha_provisoria: string }>(`/admin/contas/${c.id}/senha-provisoria`, { method: "POST" });
      setSenha({ nome: c.display_name, valor: r.senha_provisoria });
    });
  }

  async function excluir() {
    const alvo = excluindo!;
    setExcluindo(null);
    setConfirmacao("");
    await acao(() => api(`/admin/contas/${alvo.id}`, { method: "DELETE", json: { confirmar_username: alvo.username } }));
  }

  return (
    <>
      <h1>Contas</h1>
      {senha && (
        <Banner kind="success">
          Senha provisória de {senha.nome}: <strong>{senha.valor}</strong>. Anote e entregue ao professor; ela não será
          mostrada de novo. No primeiro acesso, o professor cria uma senha própria.
        </Banner>
      )}
      {error && <Banner kind="error">{error}</Banner>}
      <form className="audio-area" onSubmit={criar} aria-label="Nova conta">
        <h2>Nova conta</h2>
        <div className="form-grid">
          <TextField label="Nome de usuário" value={form.username} maxLength={64} required
            onChange={(e) => setForm({ ...form, username: e.target.value })} />
          <TextField label="Nome de exibição" value={form.display_name} maxLength={120} required
            onChange={(e) => setForm({ ...form, display_name: e.target.value })} />
          <SelectField label="Perfil" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })}>
            <option value="PROFESSOR">Professor</option>
            <option value="ADMIN_LOCAL">Administrador</option>
          </SelectField>
        </div>
        <Button type="submit">Criar conta</Button>
      </form>
      <table className="table">
        <thead>
          <tr><th>Nome</th><th>Usuário</th><th>Perfil</th><th>Situação</th><th><span className="visually-hidden">Ações</span></th></tr>
        </thead>
        <tbody>
          {contas.map((c) => (
            <tr key={c.id}>
              <td>{c.display_name}</td>
              <td>{c.username}</td>
              <td>{c.role === "ADMIN_LOCAL" ? "Administrador" : "Professor"}</td>
              <td>{c.is_active ? "Ativa" : "Desativada"}</td>
              <td>
                <Button variant="tertiary" onClick={() => void acao(() => api(`/admin/contas/${c.id}`, { method: "PATCH", json: { is_active: !c.is_active } }))}>
                  {c.is_active ? "Desativar" : "Reativar"}
                </Button>
                <Button variant="tertiary" onClick={() => void redefinir(c)}>Redefinir senha</Button>
                <Button variant="tertiary" onClick={() => setExcluindo(c)}>Excluir</Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {excluindo && (
        <Dialog title={`Excluir a conta de ${excluindo.display_name}?`} onClose={() => setExcluindo(null)}
          actions={<>
            <Button variant="tertiary" onClick={() => setExcluindo(null)}>Cancelar</Button>
            <Button onClick={() => void excluir()} disabled={confirmacao.trim().toLowerCase() !== excluindo.username}>Excluir conta</Button>
          </>}>
          <p>Todos os áudios dessa conta serão apagados e não poderão ser recuperados.</p>
          <TextField label={`Digite ${excluindo.username} para confirmar`} value={confirmacao}
            onChange={(e) => setConfirmacao(e.target.value)} />
        </Dialog>
      )}
    </>
  );
}
