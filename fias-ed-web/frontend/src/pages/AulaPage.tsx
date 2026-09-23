import { useCallback, useEffect, useState } from "react";
import { Navigate, useLocation, useNavigate, useParams } from "react-router";
import { api, ApiError, sendAndProcess } from "../api/client";
import type { Aula } from "../api/types";
import { AudioPicker } from "../app/AudioPicker";
import { formatBytes, formatDate, formatDateTime, formatDuration } from "../app/format";
import { JOB_MESSAGE } from "../app/status";
import { Banner } from "../design/components/Banner";
import { Button } from "../design/components/Button";
import { Dialog } from "../design/components/Dialog";
import { StatusBadge } from "../design/components/StatusBadge";

const PODE_TROCAR = new Set(["DRAFT", "AUDIO_IMPORTED", "AUDIO_VALIDATED", "ERROR"]);

export function AulaPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [aula, setAula] = useState<Aula | null>(null);
  // Ruling P9: mensagem de erro levada pela Nova Aula quando o upload/processar falha após criar a aula.
  const [error, setError] = useState<string | null>((location.state as { erro?: string } | null)?.erro ?? null);
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [confirmarTroca, setConfirmarTroca] = useState(false);
  const [trocando, setTrocando] = useState(false);
  const [confirmarExclusao, setConfirmarExclusao] = useState(false);

  const carregar = useCallback(async () => {
    try {
      setAula(await api<Aula>(`/aulas/${id}`));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível carregar a aula.");
    }
  }, [id]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  useEffect(() => {
    if (!aula?.job_ativo) return;
    const timer = setInterval(() => void carregar(), 3000);
    return () => clearInterval(timer);
  }, [aula?.job_ativo, carregar]);

  async function enviar() {
    if (!file) return;
    setError(null);
    setProgress(0);
    try {
      setAula(await sendAndProcess(id, file, setProgress));
      setFile(null);
      setTrocando(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível enviar o áudio.");
      await carregar();
    } finally {
      setProgress(null);
    }
  }

  async function processar() {
    try {
      setAula(await api<Aula>(`/aulas/${id}/processar`, { method: "POST" }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível processar a aula.");
    }
  }

  async function excluir() {
    setError(null);
    try {
      await api(`/aulas/${id}`, { method: "DELETE" });
      navigate("/aulas", { replace: true });
    } catch (err) {
      // Ruling P15: exclusão não deve falhar em silêncio.
      setError(err instanceof ApiError ? err.message : "Não foi possível excluir a aula.");
      setConfirmarExclusao(false);
    }
  }

  if (!aula) return error ? <Banner kind="error">{error}</Banner> : <p role="status">Carregando…</p>;

  // O sistema não decide sozinho qual voz é a do professor (§48): aula pronta para
  // essa escolha leva direto para a tela dela, em vez de ficar parada aqui.
  if (aula.status === "READY_FOR_SPEAKER_REVIEW") return <Navigate to={`/aulas/${id}/vozes`} replace />;

  const podeEnviar = !aula.job_ativo && PODE_TROCAR.has(aula.status);
  const mostrarEnvio = podeEnviar && (aula.status === "DRAFT" || aula.status === "ERROR" || trocando);

  return (
    <>
      <div className="page__header">
        <div>
          <h1>Aula de {formatDate(aula.lesson_date)}</h1>
          <p className="meta">{aula.turma.name} · {aula.disciplina.name}</p>
        </div>
        <StatusBadge status={aula.status} />
      </div>

      {aula.alterada_pelo_admin_em && (
        <Banner>Alterada pelo administrador em {formatDateTime(aula.alterada_pelo_admin_em)}.</Banner>
      )}
      {aula.job_ativo && <Banner>{JOB_MESSAGE}</Banner>}
      {aula.status === "ERROR" && aula.error_message && <Banner kind="error">{aula.error_message}</Banner>}
      {error && <Banner kind="error">{error}</Banner>}
      {aula.note && <p>{aula.note}</p>}

      {aula.audio && (
        <section className="audio-area" aria-labelledby="audio-original">
          <h2 id="audio-original">Áudio da aula</h2>
          <audio controls preload="metadata" src={`/api/aulas/${aula.id}/audio`} />
          <p className="meta">
            {aula.audio.original_filename} · <span>{formatDuration(aula.audio.duration_ms)}</span> · {formatBytes(aula.audio.size_bytes)}
          </p>
          {aula.status === "AUDIO_VALIDATED" && <p>A análise das interações estará disponível em breve.</p>}
        </section>
      )}

      {aula.status === "AUDIO_IMPORTED" && !aula.job_ativo && aula.upload_pendente && (
        <section className="audio-area">
          <p>{aula.upload_pendente.original_filename} · {formatBytes(aula.upload_pendente.size_bytes)}</p>
          <Button onClick={() => void processar()}>Processar aula</Button>
        </section>
      )}

      {mostrarEnvio && (
        <section className="audio-area" aria-labelledby="enviar-titulo">
          <h2 id="enviar-titulo">{aula.status === "DRAFT" ? "Adicionar áudio da aula" : "Enviar outro áudio"}</h2>
          <p>Selecione o arquivo de áudio gravado durante sua aula.</p>
          <AudioPicker file={file} onChange={setFile} />
          {progress !== null && <progress value={progress} max={1} aria-label="Envio do áudio" />}
          <Button onClick={() => void enviar()} disabled={!file || progress !== null}>Processar aula</Button>
        </section>
      )}

      <div className="dialog__actions">
        {podeEnviar && aula.status !== "DRAFT" && aula.status !== "ERROR" && !trocando && (
          <Button variant="secondary" onClick={() => setConfirmarTroca(true)}>Substituir áudio</Button>
        )}
        {!aula.job_ativo && <Button variant="tertiary" onClick={() => setConfirmarExclusao(true)}>Excluir aula</Button>}
      </div>

      {confirmarTroca && (
        <Dialog title="Substituir o áudio?" onClose={() => setConfirmarTroca(false)}
          actions={<>
            <Button variant="tertiary" onClick={() => setConfirmarTroca(false)}>Cancelar</Button>
            <Button onClick={() => { setConfirmarTroca(false); setTrocando(true); }}>Escolher novo áudio</Button>
          </>}>
          O arquivo anterior será apagado.
        </Dialog>
      )}
      {confirmarExclusao && (
        <Dialog title="Excluir esta aula?" onClose={() => setConfirmarExclusao(false)}
          actions={<>
            <Button variant="tertiary" onClick={() => setConfirmarExclusao(false)}>Cancelar</Button>
            <Button onClick={() => void excluir()}>Excluir definitivamente</Button>
          </>}>
          O áudio será apagado e não poderá ser recuperado.
        </Dialog>
      )}
    </>
  );
}
