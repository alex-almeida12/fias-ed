import { useState, type FormEvent } from "react";
import { useParams } from "react-router";
import { api, ApiError } from "../api/client";
import { Banner } from "../design/components/Banner";
import { Button } from "../design/components/Button";
import { TextField } from "../design/components/Field";

type Resultado = {
  id: string;
  coletado_em: string;
  origem: string;
  response_count: number;
  displayable: boolean;
  min_responses: number;
};

export function ImportarQTI() {
  const { id: cicloId = "" } = useParams();
  const [file, setFile] = useState<File | null>(null);
  // Vazio de propósito: é a data em que a turma respondeu, não a de hoje.
  const [coletadoEm, setColetadoEm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [resultado, setResultado] = useState<Resultado | null>(null);
  const [enviando, setEnviando] = useState(false);

  const pronto = Boolean(file && coletadoEm);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!pronto || !file) return;
    setError(null);
    setResultado(null);
    setEnviando(true);
    try {
      const formData = new FormData();
      formData.set("coletado_em", coletadoEm);
      formData.set("arquivo", file);
      const r = await api<Resultado>(`/ciclos/${cicloId}/qti/importar`, { method: "POST", body: formData });
      setResultado(r);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível importar o relatório.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <>
      <h1>Importar relatório do questionário</h1>
      <form onSubmit={onSubmit} noValidate>
        <div className="form-grid">
          <TextField label="Relatório (CSV)" type="file" accept=".csv" required
            onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <TextField label="Quando a turma respondeu" type="date" value={coletadoEm}
            onChange={(e) => setColetadoEm(e.target.value)} required />
        </div>
        {error && <Banner kind="error">{error}</Banner>}
        {resultado && resultado.displayable && (
          <Banner kind="success">{resultado.response_count} respostas entraram no acompanhamento.</Banner>
        )}
        {resultado && !resultado.displayable && (
          <Banner kind="info">
            {resultado.response_count} respostas entraram no acompanhamento. É preciso pelo menos{" "}
            {resultado.min_responses} respostas da turma para exibir o resultado.
          </Banner>
        )}
        <Button type="submit" disabled={!pronto || enviando}>Enviar</Button>
      </form>
    </>
  );
}
