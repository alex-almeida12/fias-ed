import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { api, ApiError, sendAndProcess } from "../api/client";
import type { Aula, Disciplina, Turma } from "../api/types";
import { AudioPicker } from "../app/AudioPicker";
import { localDateInput } from "../app/format";
import { Banner } from "../design/components/Banner";
import { Button } from "../design/components/Button";
import { SelectField, TextAreaField, TextField } from "../design/components/Field";
import { NovaTurma } from "./NovaTurma";

export function NovaAula() {
  const navigate = useNavigate();
  const [turmas, setTurmas] = useState<Turma[]>([]);
  const [disciplinas, setDisciplinas] = useState<Disciplina[]>([]);
  const [turmaId, setTurmaId] = useState("");
  const [disciplinaId, setDisciplinaId] = useState("");
  const [novaDisciplina, setNovaDisciplina] = useState("");
  const [data, setData] = useState(() => localDateInput());
  const [nota, setNota] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Ruling P15: erro ao carregar turmas/disciplinas não deve ficar silencioso.
    api<Turma[]>("/turmas").then(setTurmas).catch((err) =>
      setError(err instanceof ApiError ? err.message : "Não foi possível carregar as turmas."));
    api<Disciplina[]>("/disciplinas").then(setDisciplinas).catch((err) =>
      setError(err instanceof ApiError ? err.message : "Não foi possível carregar as disciplinas."));
  }, []);

  async function salvarDisciplina() {
    setError(null);
    try {
      const d = await api<Disciplina>("/disciplinas", { method: "POST", json: { name: novaDisciplina } });
      setDisciplinas([...disciplinas, d]);
      setDisciplinaId(d.id);
      setNovaDisciplina("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível salvar a disciplina.");
    }
  }

  const pronto = turmaId && turmaId !== "__nova__" && disciplinaId && disciplinaId !== "__nova__" && data && file;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!pronto || !file) return;
    setError(null);
    let aula: Aula | null = null;
    try {
      aula = await api<Aula>("/aulas", { method: "POST", json: {
        turma_id: turmaId, disciplina_id: disciplinaId, lesson_date: data, note: nota || null } });
      setProgress(0);
      await sendAndProcess(aula.id, file, setProgress);
      navigate(`/aulas/${aula.id}`);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Não foi possível salvar a aula.";
      // Ruling P9: a aula já foi criada, mas o upload/processar falhou (413, 415, 409...).
      // Leva a mensagem para a página da Aula via navigation state, em vez de perdê-la.
      if (aula) return navigate(`/aulas/${aula.id}`, { state: { erro: message } });
      setError(message);
      setProgress(null);
    }
  }

  return (
    <>
      <h1>Nova aula</h1>
      <form onSubmit={onSubmit} noValidate>
        <div className="form-grid">
          <SelectField label="Turma" value={turmaId} onChange={(e) => setTurmaId(e.target.value)} required>
            <option value="" disabled>Escolha a turma</option>
            {turmas.map((t) => <option key={t.id} value={t.id}>{t.name} — {t.escola.name}</option>)}
            <option value="__nova__">+ Cadastrar nova turma</option>
          </SelectField>
          <SelectField label="Disciplina" value={disciplinaId} onChange={(e) => setDisciplinaId(e.target.value)} required>
            <option value="" disabled>Escolha a disciplina</option>
            {disciplinas.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            <option value="__nova__">+ Cadastrar nova disciplina</option>
          </SelectField>
        </div>
        {turmaId === "__nova__" && (
          <NovaTurma onCancel={() => setTurmaId("")} onCreated={(t) => { setTurmas([...turmas, t]); setTurmaId(t.id); }} />
        )}
        {disciplinaId === "__nova__" && (
          <div className="audio-area">
            <TextField label="Nome da disciplina" value={novaDisciplina} maxLength={120}
              onChange={(e) => setNovaDisciplina(e.target.value)} />
            <Button variant="secondary" onClick={() => void salvarDisciplina()} disabled={!novaDisciplina.trim()}>
              Salvar disciplina
            </Button>
          </div>
        )}
        <div className="form-grid">
          <TextField label="Data" type="date" value={data} onChange={(e) => setData(e.target.value)} required />
          <TextAreaField label="Observação (opcional)" value={nota} maxLength={2000} onChange={(e) => setNota(e.target.value)} />
        </div>
        <section className="audio-area" aria-labelledby="audio-titulo">
          <h2 id="audio-titulo">Adicionar áudio da aula</h2>
          <p>Selecione o arquivo de áudio gravado durante sua aula.</p>
          <AudioPicker file={file} onChange={setFile} />
          {progress !== null && <progress value={progress} max={1} aria-label="Envio do áudio" />}
        </section>
        {error && <Banner kind="error">{error}</Banner>}
        <Button type="submit" disabled={!pronto || progress !== null}>Processar aula</Button>
      </form>
    </>
  );
}
