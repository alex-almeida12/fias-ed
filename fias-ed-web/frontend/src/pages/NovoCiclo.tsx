import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { api, ApiError } from "../api/client";
import type { Disciplina, Turma } from "../api/types";
import { localDateInput } from "../app/format";
import { Banner } from "../design/components/Banner";
import { Button } from "../design/components/Button";
import { SelectField, TextField } from "../design/components/Field";

export function NovoCiclo() {
  const navigate = useNavigate();
  const [turmas, setTurmas] = useState<Turma[]>([]);
  const [disciplinas, setDisciplinas] = useState<Disciplina[]>([]);
  const [turmaId, setTurmaId] = useState("");
  const [disciplinaId, setDisciplinaId] = useState("");
  const [inicio, setInicio] = useState(() => localDateInput());
  const [nAulas, setNAulas] = useState("10");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    // Ruling P15: erro ao carregar turmas/disciplinas não deve ficar silencioso.
    api<Turma[]>("/turmas").then(setTurmas).catch((err) =>
      setError(err instanceof ApiError ? err.message : "Não foi possível carregar as turmas."));
    api<Disciplina[]>("/disciplinas").then(setDisciplinas).catch((err) =>
      setError(err instanceof ApiError ? err.message : "Não foi possível carregar as disciplinas."));
  }, []);

  const n = Number(nAulas);
  const pronto = turmaId && disciplinaId && inicio && Number.isInteger(n) && n >= 1;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!pronto) return;
    setError(null);
    setEnviando(true);
    try {
      await api("/ciclos", { method: "POST", json: {
        turma_id: turmaId, disciplina_id: disciplinaId, n_aulas_previstas: n, iniciado_em: inicio } });
      navigate("/aulas");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível começar o acompanhamento.");
      setEnviando(false);
    }
  }

  return (
    <>
      <h1>Começar um acompanhamento</h1>
      <form onSubmit={onSubmit} noValidate>
        <div className="form-grid">
          <SelectField label="Turma" value={turmaId} onChange={(e) => setTurmaId(e.target.value)} required>
            <option value="" disabled>Escolha a turma</option>
            {turmas.map((t) => <option key={t.id} value={t.id}>{t.name} — {t.escola.name}</option>)}
          </SelectField>
          <SelectField label="Disciplina" value={disciplinaId} onChange={(e) => setDisciplinaId(e.target.value)} required>
            <option value="" disabled>Escolha a disciplina</option>
            {disciplinas.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </SelectField>
        </div>
        <div className="form-grid">
          <TextField label="Quantas aulas você quer acompanhar?" type="number" min={1} value={nAulas}
            onChange={(e) => setNAulas(e.target.value)} required />
          <TextField label="Início do acompanhamento" type="date" value={inicio}
            onChange={(e) => setInicio(e.target.value)} required />
        </div>
        {error && <Banner kind="error">{error}</Banner>}
        <Button type="submit" disabled={!pronto || enviando}>Começar</Button>
      </form>
    </>
  );
}
