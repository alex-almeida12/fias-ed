import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { api, ApiError } from "../../api/client";
import type { AulaResumo, Conta, Me } from "../../api/types";
import { useAuth } from "../../app/AuthContext";
import { formatDate } from "../../app/format";
import { Banner } from "../../design/components/Banner";
import { Button } from "../../design/components/Button";
import { EmptyState } from "../../design/components/EmptyState";
import { SelectField } from "../../design/components/Field";
import { StatusBadge } from "../../design/components/StatusBadge";

export function AdminAulas() {
  const { setMe } = useAuth();
  const navigate = useNavigate();
  const [contas, setContas] = useState<Conta[]>([]);
  const [filtro, setFiltro] = useState("");
  const [aulas, setAulas] = useState<AulaResumo[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Ruling P15: carregamento não deve falhar em silêncio.
  useEffect(() => {
    api<Conta[]>("/admin/contas")
      .then(setContas)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Não foi possível carregar os professores."));
  }, []);
  useEffect(() => {
    api<AulaResumo[]>(filtro ? `/admin/aulas?professor_id=${filtro}` : "/admin/aulas")
      .then(setAulas)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Não foi possível carregar as aulas."));
  }, [filtro]);

  async function agirComo(aula: AulaResumo) {
    setError(null);
    try {
      setMe(await api<Me>("/admin/agir-como", { method: "POST", json: { professor_id: aula.professor!.id } }));
      navigate(`/aulas/${aula.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível agir como este professor.");
    }
  }

  return (
    <>
      <h1>Aulas dos professores</h1>
      {error && <Banner kind="error">{error}</Banner>}
      <SelectField label="Professor" value={filtro} onChange={(e) => setFiltro(e.target.value)}>
        <option value="">Todos</option>
        {contas.map((c) => <option key={c.id} value={c.id}>{c.display_name}</option>)}
      </SelectField>
      {aulas.length === 0 ? (
        <EmptyState title="Nenhuma aula encontrada">Quando os professores adicionarem aulas, elas aparecem aqui.</EmptyState>
      ) : (
        <ul className="list">
          {aulas.map((a) => (
            <li key={a.id} className="list__item">
              <div>
                <strong>{a.professor?.display_name}</strong>
                <p className="meta">{formatDate(a.lesson_date)} · {a.turma.name} · {a.disciplina.name}</p>
              </div>
              <StatusBadge status={a.status} />
              <Button variant="secondary" onClick={() => void agirComo(a)}>Agir como {a.professor?.display_name}</Button>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
