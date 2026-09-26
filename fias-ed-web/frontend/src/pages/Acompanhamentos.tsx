import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import { api, ApiError } from "../api/client";
import type { Ciclo } from "../api/types";
import { formatDate } from "../app/format";
import { Banner } from "../design/components/Banner";
import { Button } from "../design/components/Button";
import { Dialog } from "../design/components/Dialog";
import { EmptyState } from "../design/components/EmptyState";

export function Acompanhamentos() {
  const [acompanhamentos, setAcompanhamentos] = useState<Ciclo[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [encerrando, setEncerrando] = useState<Ciclo | null>(null);

  // Reaproveitada após encerrar (Task 18): a resposta de POST /ciclos/{id}/encerrar não tem o
  // formato de Ciclo (traz turma_id/disciplina_id, não os objetos turma/disciplina) — em vez de
  // remontar a lista a partir dela, buscamos a lista de novo pela rota já testada.
  const carregar = useCallback(() => {
    return api<Ciclo[]>("/ciclos").then(setAcompanhamentos).catch((err) =>
      setError(err instanceof ApiError ? err.message : "Não foi possível carregar os acompanhamentos. Recarregue a página."));
  }, []);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  async function encerrar() {
    const alvo = encerrando!;
    setEncerrando(null);
    setError(null);
    try {
      await api(`/ciclos/${alvo.id}/encerrar`, { method: "POST" });
      await carregar();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível encerrar o acompanhamento.");
    }
  }

  const comecar = <Link className="btn btn--primary" to="/ciclos/novo">Começar um acompanhamento</Link>;

  return (
    <>
      <div className="page__header">
        <h1>Meus acompanhamentos</h1>
        {acompanhamentos && acompanhamentos.length > 0 && comecar}
      </div>
      {error && <Banner kind="error">{error}</Banner>}
      {acompanhamentos === null && !error && <p role="status">Carregando…</p>}
      {acompanhamentos?.length === 0 && (
        <EmptyState title="Nenhum acompanhamento ainda" action={comecar}>
          Um acompanhamento reúne as aulas de uma turma ao longo do tempo, para você enviar o questionário
          respondido pelos estudantes e ver a trajetória.
        </EmptyState>
      )}
      {acompanhamentos && acompanhamentos.length > 0 && (
        <ul className="list">
          {acompanhamentos.map((c) => (
            <li key={c.id} className="list__item">
              <div>
                <p>{c.turma.name} · {c.disciplina.name}</p>
                <p className="meta">
                  Início em {formatDate(c.iniciado_em)} ·{" "}
                  {c.encerrado_em ? `Encerrado em ${formatDate(c.encerrado_em)}` : "Em andamento"} ·{" "}
                  {c.n_aulas_previstas} aulas previstas
                </p>
                <p className="meta">
                  <Link to={`/ciclos/${c.id}/relatorio`}>Ver o acompanhamento</Link>
                  {" · "}
                  <Link to={`/ciclos/${c.id}/qti`}>Enviar o relatório do questionário</Link>
                  {!c.encerrado_em && (
                    <>
                      {" · "}
                      <Button variant="tertiary" onClick={() => setEncerrando(c)}>Encerrar acompanhamento</Button>
                    </>
                  )}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
      {encerrando && (
        <Dialog title={`Encerrar o acompanhamento de ${encerrando.turma.name}?`} onClose={() => setEncerrando(null)}
          actions={<>
            <Button variant="tertiary" onClick={() => setEncerrando(null)}>Cancelar</Button>
            <Button onClick={() => void encerrar()}>Confirmar encerramento</Button>
          </>}>
          <p>
            A última aula passa a precisar do questionário respondido pelos estudantes para gerar o relatório —
            é ela que fecha a comparação com o começo.
          </p>
          <p>Isto não pode ser desfeito por aqui.</p>
        </Dialog>
      )}
    </>
  );
}
