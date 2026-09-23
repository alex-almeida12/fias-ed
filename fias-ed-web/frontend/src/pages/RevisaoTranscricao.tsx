import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { api, ApiError } from "../api/client";
import type { Papel, Segmento, TranscricaoBloco } from "../api/types";
import { formatTimestamp } from "../app/format";
import { Banner } from "../design/components/Banner";
import { Button } from "../design/components/Button";
import { TextAreaField } from "../design/components/Field";

function proximoPapel(papel: Papel): Papel {
  return papel === "PROFESSOR" ? "ALUNO" : "PROFESSOR";
}

type CamposEditaveis = Partial<{ texto: string; papel: Papel }>;

type SegmentoLinhaProps = { seg: Segmento; aulaId: string; onSalvo: (atualizado: Segmento) => void };

function SegmentoLinha({ seg, aulaId, onSalvo }: SegmentoLinhaProps) {
  const [texto, setTexto] = useState(seg.texto);
  const [erro, setErro] = useState<string | null>(null);
  const horario = formatTimestamp(seg.start_ms);

  async function salvar(campos: CamposEditaveis) {
    setErro(null);
    try {
      const atualizado = await api<Segmento>(`/segmentos/${seg.id}`, {
        method: "PATCH",
        json: { ...campos, version: seg.version },
      });
      onSalvo(atualizado);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Não foi possível salvar este trecho.");
    }
  }

  return (
    <section className="segmento" role="group" aria-label={`Trecho de ${horario}`}>
      <div className="segmento__cabecalho">
        <p className="meta">{horario}</p>
        {/* spec §8.3: "ouvir é como se conserta atribuição errada" — o professor decide
           quem falou pelo áudio, não adivinhando pelo texto do ASR. `preload="none"`
           porque um bloco de cinco minutos tem dezenas de trechos: sem isto o navegador
           baixaria (e o servidor recortaria com ffmpeg) todos eles ao abrir a página. */}
        <audio controls preload="none" aria-label={`Áudio do trecho de ${horario}`}
          src={`/api/aulas/${aulaId}/audio?inicio_ms=${seg.start_ms}&fim_ms=${seg.end_ms}`} />
        <Button variant="secondary" aria-pressed={seg.papel === "ALUNO"}
          onClick={() => void salvar({ papel: proximoPapel(seg.papel) })}>
          {seg.papel === "PROFESSOR" ? "Você — marcar como ALUNO" : "ALUNO — marcar como você"}
        </Button>
      </div>
      <TextAreaField label={`Texto do trecho de ${horario}`} value={texto}
        onChange={(e) => setTexto(e.target.value)}
        // O PATCH só sai quando o texto de fato mudou — sair do campo sem editar nada
        // não pode inflar `Segmento.revisado` (regra 2 do brief da Task 10).
        onBlur={() => { if (texto !== seg.texto) void salvar({ texto }); }} />
      {erro && <Banner kind="error">{erro}</Banner>}
    </section>
  );
}

export function RevisaoTranscricao() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const [bloco, setBloco] = useState(0);
  const [dados, setDados] = useState<TranscricaoBloco | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [statusSalvo, setStatusSalvo] = useState("");
  const [concluindo, setConcluindo] = useState(false);

  const carregar = useCallback(async (numeroDoBloco: number) => {
    try {
      const resposta = await api<TranscricaoBloco>(`/aulas/${id}/transcricao?bloco=${numeroDoBloco}`);
      setDados(resposta);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Não foi possível carregar a transcrição desta aula.");
    }
  }, [id]);

  useEffect(() => {
    setDados(null);
    void carregar(bloco);
  }, [carregar, bloco]);

  function aoSalvarSegmento(atualizado: Segmento) {
    setDados((prev) => prev && { ...prev, segmentos: prev.segmentos.map((s) => (s.id === atualizado.id ? atualizado : s)) });
    setStatusSalvo(`Trecho de ${formatTimestamp(atualizado.start_ms)} salvo.`);
  }

  async function concluir() {
    setErro(null);
    setConcluindo(true);
    try {
      await api(`/aulas/${id}/transcricao/concluir`, { method: "POST" });
      navigate(`/aulas/${id}`, { replace: true });
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Não foi possível concluir a revisão.");
      setConcluindo(false);
    }
  }

  return (
    <>
      <div className="page__header">
        <div>
          <h1>Revise a transcrição, se quiser</h1>
          <p>
            Leia o que ficou registrado da sua aula. Corrija o texto ou troque quem falou onde precisar
            — ou siga sem mexer em nada, a revisão não é obrigatória.
          </p>
        </div>
        <Button onClick={() => void concluir()} disabled={concluindo}>Está bom assim, seguir</Button>
      </div>

      <p className="visually-hidden" role="status">{statusSalvo}</p>
      {erro && <Banner kind="error">{erro}</Banner>}
      {dados === null && !erro && <p role="status">Carregando…</p>}

      {dados && (
        <>
          <nav className="bloco-nav" aria-label="Navegação por blocos de cinco minutos">
            <Button variant="secondary" onClick={() => setBloco((b) => b - 1)} disabled={dados.bloco === 0}>
              5 minutos anteriores
            </Button>
            <p className="meta">Bloco {dados.bloco + 1} de {dados.blocos}</p>
            <Button variant="secondary" onClick={() => setBloco((b) => b + 1)} disabled={dados.bloco + 1 >= dados.blocos}>
              Próximos 5 minutos
            </Button>
          </nav>

          {dados.segmentos.length === 0 && <p>Nenhum trecho de fala neste bloco.</p>}

          <div className="segmentos">
            {dados.segmentos.map((seg) => (
              <SegmentoLinha key={seg.id} seg={seg} aulaId={id} onSalvo={aoSalvarSegmento} />
            ))}
          </div>
        </>
      )}
    </>
  );
}
