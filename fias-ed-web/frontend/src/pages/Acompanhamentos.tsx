import { useEffect, useState } from "react";
import { Link } from "react-router";
import { api, ApiError } from "../api/client";
import type { Ciclo } from "../api/types";
import { formatDate } from "../app/format";
import { Banner } from "../design/components/Banner";
import { EmptyState } from "../design/components/EmptyState";

export function Acompanhamentos() {
  const [acompanhamentos, setAcompanhamentos] = useState<Ciclo[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Ciclo[]>("/ciclos").then(setAcompanhamentos).catch((err) =>
      setError(err instanceof ApiError ? err.message : "Não foi possível carregar os acompanhamentos. Recarregue a página."));
  }, []);

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
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
