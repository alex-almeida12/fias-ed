import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { Escola, Turma } from "../api/types";
import { Banner } from "../design/components/Banner";
import { Button } from "../design/components/Button";
import { SelectField, TextField } from "../design/components/Field";

const REGIOES = ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"];

type Props = { onCreated: (turma: Turma) => void; onCancel: () => void };

export function NovaTurma({ onCreated, onCancel }: Props) {
  const [escolas, setEscolas] = useState<Escola[]>([]);
  const [nome, setNome] = useState("");
  const [escolaId, setEscolaId] = useState("");
  const [novaEscola, setNovaEscola] = useState({ name: "", municipality: "", region: "" });
  const [duplicatas, setDuplicatas] = useState<Escola[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Escola[]>("/escolas").then(setEscolas).catch((err) =>
      setError(err instanceof ApiError ? err.message : "Não foi possível carregar as escolas."));
  }, []);

  // Ruling P15: cada chamada que cria/usa uma turma trata seu próprio erro (não falha em silêncio),
  // tanto quando disparada por "salvar" quanto pelo botão "Usar <escola>".
  async function criarTurma(idDaEscola: string) {
    try {
      onCreated(await api<Turma>("/turmas", { method: "POST", json: { name: nome, escola_id: idDaEscola } }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível salvar a turma.");
    }
  }

  async function salvar(confirmarNova = false) {
    setError(null);
    if (escolaId !== "__nova__") {
      void criarTurma(escolaId);
      return;
    }
    try {
      const escola = await api<Escola>("/escolas", { method: "POST", json: {
        name: novaEscola.name, municipality: novaEscola.municipality || null,
        region: novaEscola.region || null, confirmar_nova: confirmarNova } });
      await criarTurma(escola.id);
    } catch (err) {
      if (err instanceof ApiError && err.code === "ESCOLA_DUPLICADA") setDuplicatas(err.extra.duplicatas as Escola[]);
      setError(err instanceof ApiError ? err.message : "Não foi possível salvar a turma.");
    }
  }

  return (
    <div className="audio-area" role="group" aria-label="Nova turma">
      <TextField label="Nome da turma" value={nome} onChange={(e) => setNome(e.target.value)} maxLength={120} required />
      <SelectField label="Escola" value={escolaId} onChange={(e) => setEscolaId(e.target.value)} required>
        <option value="" disabled>Escolha a escola</option>
        {escolas.map((esc) => <option key={esc.id} value={esc.id}>{esc.name}{esc.municipality ? ` (${esc.municipality})` : ""}</option>)}
        <option value="__nova__">+ Cadastrar nova escola</option>
      </SelectField>
      {escolaId === "__nova__" && (
        <div className="form-grid">
          <TextField label="Nome da escola" value={novaEscola.name} maxLength={200} required
            onChange={(e) => setNovaEscola({ ...novaEscola, name: e.target.value })} />
          <TextField label="Município" value={novaEscola.municipality} maxLength={120}
            onChange={(e) => setNovaEscola({ ...novaEscola, municipality: e.target.value })} />
          <SelectField label="Região" value={novaEscola.region}
            onChange={(e) => setNovaEscola({ ...novaEscola, region: e.target.value })}>
            <option value="">Não informar</option>
            {REGIOES.map((r) => <option key={r} value={r}>{r}</option>)}
          </SelectField>
        </div>
      )}
      {error && <Banner kind="error">{error}</Banner>}
      {duplicatas.length > 0 && (
        <div className="dialog__actions">
          {duplicatas.map((d) => (
            <Button key={d.id} variant="secondary" onClick={() => void criarTurma(d.id)}>
              Usar {d.name}{d.municipality ? ` (${d.municipality})` : ""}
            </Button>
          ))}
          <Button variant="tertiary" onClick={() => void salvar(true)}>Cadastrar mesmo assim</Button>
        </div>
      )}
      <div className="dialog__actions">
        <Button variant="tertiary" onClick={onCancel}>Cancelar</Button>
        <Button onClick={() => void salvar()}>Salvar turma</Button>
      </div>
    </div>
  );
}
