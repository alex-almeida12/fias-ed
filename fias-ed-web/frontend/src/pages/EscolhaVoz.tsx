import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { api, ApiError } from "../api/client";
import type { Voz } from "../api/types";
import { formatDuration, formatTimestamp } from "../app/format";
import { Banner } from "../design/components/Banner";
import { Button } from "../design/components/Button";

export function EscolhaVoz() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const [vozes, setVozes] = useState<Voz[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [escolhendo, setEscolhendo] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    try {
      const resposta = await api<{ vozes: Voz[] }>(`/aulas/${id}/vozes`);
      setVozes(resposta.vozes);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível carregar as vozes desta aula.");
    }
  }, [id]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  async function escolher(rotulo: string) {
    setError(null);
    setEscolhendo(rotulo);
    try {
      await api(`/aulas/${id}/vozes/escolher`, { method: "POST", json: { rotulo } });
      navigate(`/aulas/${id}`, { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível registrar sua escolha.");
      setEscolhendo(null);
    }
  }

  return (
    <>
      <h1>Qual destas vozes é você?</h1>
      {/* Antes da escolha o sistema não sabe quem é quem: nenhuma voz pode ser
         chamada de "aluno" aqui, nem na numeração nem no texto de instrução. */}
      <p>Ouça os trechos e aponte qual voz é a sua. As demais ficam agrupadas, sem identificação individual.</p>
      {error && <Banner kind="error">{error}</Banner>}
      {vozes === null && !error && <p role="status">Carregando…</p>}
      {vozes && (
        <ul className="list">
          {vozes.map((v, i) => (
            <li key={v.rotulo} className="list__item">
              <div>
                <h2>Voz {i + 1}</h2>
                <p className="meta">{formatDuration(v.tempo_total_ms)} de fala · {v.n_segmentos} momentos</p>
                {v.amostras.map((a) => (
                  <audio key={a.inicio_ms} controls preload="none"
                    aria-label={`Trecho da voz ${i + 1} em ${formatTimestamp(a.inicio_ms)}`}
                    src={`/api/aulas/${id}/audio?inicio_ms=${a.inicio_ms}&fim_ms=${a.fim_ms}`} />
                ))}
              </div>
              <Button onClick={() => void escolher(v.rotulo)} disabled={escolhendo !== null}>
                Esta voz é a minha
              </Button>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
