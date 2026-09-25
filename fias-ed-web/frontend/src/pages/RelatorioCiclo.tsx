import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router";
import { api, ApiError } from "../api/client";
import type { CicloRelatorio, Indice, TrajetoriaItem } from "../api/types";
import { formatDate } from "../app/format";
import { statusText } from "../app/status";
import { Banner } from "../design/components/Banner";

// Mesmo texto de PadroesInteracao.tsx e RelatorioAula.tsx: `valor: null` não é
// zero, é "não houve trechos suficientes para calcular" — inventar um zero
// aqui apagaria essa diferença.
function formatValorIndice(valor: number | null): string {
  if (valor === null) return "Sem trechos suficientes nesta aula para calcular.";
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(valor);
}

function formatOctante(valor: number): string {
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(valor);
}

// As colunas de índice vêm da primeira aula já classificada: `indices_payload`
// (backend) devolve sempre o conjunto inteiro de índices das regras quando a
// aula tem classificação, então qualquer aula não vazia serve de referência
// para o cabeçalho. Se nenhuma aula do ciclo tiver sido classificada ainda,
// não há como saber os nomes das colunas — a tabela fica só com Data e
// Situação, porque isso é tudo que a API mandou.
function colunasDeIndice(trajetoria: TrajetoriaItem[]): Indice[] {
  return trajetoria.find((item) => item.indices.length > 0)?.indices ?? [];
}

export function RelatorioCiclo() {
  const { id = "" } = useParams();
  const [dados, setDados] = useState<CicloRelatorio | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    try {
      const resposta = await api<CicloRelatorio>(`/ciclos/${id}/relatorio`);
      setDados(resposta);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Não foi possível carregar o relatório deste ciclo.");
    }
  }, [id]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  const colunas = dados ? colunasDeIndice(dados.trajetoria) : [];

  return (
    <>
      <h1>Relatório do ciclo</h1>
      {erro && <Banner kind="error">{erro}</Banner>}
      {dados === null && !erro && <p role="status">Carregando…</p>}

      {dados && (
        <>
          <p className="meta">{dados.ciclo.turma.name} · {dados.ciclo.disciplina.name}</p>
          <p className="meta">
            Início em {formatDate(dados.ciclo.iniciado_em)} ·{" "}
            {dados.ciclo.encerrado_em ? `Encerrado em ${formatDate(dados.ciclo.encerrado_em)}` : "Em andamento"}
          </p>
          <p>{dados.n_aulas_realizadas} de {dados.ciclo.n_aulas_previstas} aulas acompanhadas</p>

          <section>
            <h2>Trajetória</h2>
            {dados.trajetoria.length === 0 && <p>Ainda não há aulas neste ciclo.</p>}
            {dados.trajetoria.length > 0 && (
              // Uma coluna por índice: em 360px a tabela não cabe (medido em
              // navegador). A saída é rolagem contida à tabela — nunca um gráfico
              // de linha, que afirmaria melhora que o sistema não afirma (ver
              // brief da Task 15). Mesmo padrão de .tabela-rolante já usado na
              // matriz de transições.
              <div className="tabela-rolante">
                <table className="table">
                  <caption>Trajetória do ciclo: uma linha por aula, na ordem em que aconteceram.</caption>
                  <thead>
                    <tr>
                      <th scope="col">Data</th>
                      <th scope="col">Situação</th>
                      {colunas.map((idx) => <th key={idx.codigo} scope="col">{idx.nome}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {dados.trajetoria.map((item) => (
                      <tr key={item.aula_id}>
                        <th scope="row">{formatDate(item.lesson_date)}</th>
                        <td>{statusText(item.status)}</td>
                        {item.indices.length === 0
                          ? colunas.length > 0 && <td colSpan={colunas.length}>Ainda sem análise.</td>
                          : item.indices.map((idx) => <td key={idx.codigo}>{formatValorIndice(idx.valor)}</td>)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section>
            <h2>Questionário respondido pelos estudantes</h2>
            {dados.coletas.length === 0 && <Banner>A turma ainda não respondeu ao questionário.</Banner>}
            {dados.coletas.length > 0 && (
              <ul className="list">
                {dados.coletas.map((c) => (
                  <li key={c.id} className="list__item observacao">
                    <p className="meta">{formatDate(c.coletado_em)} · {c.response_count} respostas</p>
                    {c.displayable ? (
                      <ul>
                        {c.octantes.map((o) => (
                          <li key={o.octant}>{o.label}: {formatOctante(o.value)}</li>
                        ))}
                      </ul>
                    ) : (
                      <p>Poucas respostas para exibir o resultado.</p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </>
  );
}
