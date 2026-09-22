import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../../api/client";
import type { Escola } from "../../api/types";
import { Banner } from "../../design/components/Banner";
import { Button } from "../../design/components/Button";
import { SelectField, TextField } from "../../design/components/Field";

// Ruling P8: valores aceitos pelo backend (app/models.py REGIONS, catalog/routes.py Regiao).
const REGIOES = ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"];

function LinhaEscola({ escola, outras, onChange }: { escola: Escola; outras: Escola[]; onChange: () => Promise<void> }) {
  const [nome, setNome] = useState(escola.name);
  const [municipio, setMunicipio] = useState(escola.municipality ?? "");
  const [regiao, setRegiao] = useState(escola.region ?? "");
  const [destino, setDestino] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function run(fn: () => Promise<unknown>) {
    setError(null);
    try {
      await fn();
      await onChange();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível concluir a ação.");
    }
  }

  return (
    <tr>
      <td><TextField label="Nome" value={nome} onChange={(e) => setNome(e.target.value)} maxLength={200} /></td>
      <td><TextField label="Município" value={municipio} onChange={(e) => setMunicipio(e.target.value)} maxLength={120} /></td>
      <td>
        <SelectField label="Região" value={regiao} onChange={(e) => setRegiao(e.target.value)}>
          <option value="">Sem região</option>
          {REGIOES.map((r) => <option key={r} value={r}>{r}</option>)}
        </SelectField>
      </td>
      <td>
        <Button variant="tertiary" onClick={() => void run(() => api(`/admin/escolas/${escola.id}`, { method: "PATCH",
          json: { name: nome, municipality: municipio || null, region: regiao || null } }))}>
          Salvar
        </Button>
      </td>
      <td>
        <SelectField label="Juntar com" value={destino} onChange={(e) => setDestino(e.target.value)}>
          <option value="">Escolha a escola que fica</option>
          {outras.map((o) => <option key={o.id} value={o.id}>{o.name}{o.municipality ? ` (${o.municipality})` : ""}</option>)}
        </SelectField>
        <Button variant="tertiary" disabled={!destino}
          onClick={() => void run(() => api(`/admin/escolas/${escola.id}/juntar`, { method: "POST", json: { destino_id: destino } }))}>
          Juntar
        </Button>
        {error && <Banner kind="error">{error}</Banner>}
      </td>
    </tr>
  );
}

export function Escolas() {
  const [escolas, setEscolas] = useState<Escola[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Ruling P15: carregamento não deve falhar em silêncio; limpa erro anterior antes de tentar
  // de novo, para um recarregamento bem-sucedido apagar o aviso de uma falha anterior.
  const carregar = useCallback(async () => {
    setError(null);
    try {
      setEscolas(await api<Escola[]>("/escolas"));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível carregar as escolas.");
    }
  }, []);
  useEffect(() => {
    void carregar();
  }, [carregar]);

  return (
    <>
      <h1>Escolas</h1>
      <p>Corrija nomes e junte escolas cadastradas em duplicidade. As turmas da escola juntada passam para a escola que fica.</p>
      {error && <Banner kind="error">{error}</Banner>}
      <table className="table table--campos">
        <thead>
          <tr><th>Nome</th><th>Município</th><th>Região</th><th><span className="visually-hidden">Salvar</span></th><th>Duplicidade</th></tr>
        </thead>
        <tbody>
          {escolas.map((e) => (
            <LinhaEscola key={e.id} escola={e} outras={escolas.filter((o) => o.id !== e.id)} onChange={carregar} />
          ))}
        </tbody>
      </table>
    </>
  );
}
