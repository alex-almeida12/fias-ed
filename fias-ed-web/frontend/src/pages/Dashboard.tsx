import { useEffect, useState } from "react";
import { Link } from "react-router";
import { api, ApiError } from "../api/client";
import type { AulaResumo } from "../api/types";
import { useAuth } from "../app/AuthContext";
import { formatDate } from "../app/format";
import { Banner } from "../design/components/Banner";
import { EmptyState } from "../design/components/EmptyState";
import { StatusBadge } from "../design/components/StatusBadge";

export function Dashboard() {
  const { me } = useAuth();
  const [aulas, setAulas] = useState<AulaResumo[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<AulaResumo[]>("/aulas").then(setAulas).catch((err) =>
      setError(err instanceof ApiError ? err.message : "Não foi possível carregar as aulas. Recarregue a página."));
  }, [me?.acting_as?.id]);

  const adicionar = <Link className="btn btn--primary" to="/aulas/nova">Adicionar aula</Link>;
  return (
    <>
      <div className="page__header">
        <h1>{me?.acting_as ? `Aulas de ${me.acting_as.display_name}` : "Minhas aulas"}</h1>
        {aulas && aulas.length > 0 && adicionar}
      </div>
      {error && <Banner kind="error">{error}</Banner>}
      {aulas === null && !error && <p role="status">Carregando…</p>}
      {aulas?.length === 0 && (
        <EmptyState title="Nenhuma aula ainda" action={adicionar}>
          Adicione sua primeira aula e envie o áudio gravado em sala.
        </EmptyState>
      )}
      {aulas && aulas.length > 0 && (
        <ul className="list">
          {aulas.map((a) => (
            <li key={a.id} className="list__item">
              <div>
                <Link to={`/aulas/${a.id}`}>Aula de {formatDate(a.lesson_date)}</Link>
                <p className="meta">{a.turma.name} · {a.disciplina.name}</p>
              </div>
              <StatusBadge status={a.status} />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
