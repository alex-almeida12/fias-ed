import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router";
import { api, ApiError } from "../api/client";
import type { Padroes } from "../api/types";
import { formatTimestamp } from "../app/format";
import { Banner } from "../design/components/Banner";
import { FaixaDeTempo } from "../design/components/FaixaDeTempo";

const CATEGORIAS = Array.from({ length: 10 }, (_, i) => i + 1);

function formatValor(valor: number | null): string {
  if (valor === null) return "Sem trechos suficientes nesta aula para calcular.";
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(valor);
}

export function PadroesInteracao() {
  const { id = "" } = useParams();
  const [dados, setDados] = useState<Padroes | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    try {
      const resposta = await api<Padroes>(`/aulas/${id}/padroes`);
      setDados(resposta);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Não foi possível carregar os padrões de interação desta aula.");
    }
  }, [id]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  return (
    <>
      <h1>Padrões de interação</h1>
      {erro && <Banner kind="error">{erro}</Banner>}
      {dados === null && !erro && <p role="status">Carregando…</p>}

      {dados && (
        <>
          {/* Ordem de leitura da spec §8.4: o que ajuda a entender vem primeiro
             (faixa e observações), o dado técnico vem depois — matriz e índices,
             tudo na mesma página, nada recolhido. */}
          <section>
            <h2>Como a aula se distribuiu ao longo do tempo</h2>
            <FaixaDeTempo faixa={dados.faixa} />
          </section>

          <section>
            <h2>Observações da aula</h2>
            {dados.observacoes.length === 0 && <p>Não há observações para esta aula.</p>}
            <ul className="list">
              {dados.observacoes.map((obs, i) => (
                <li key={i} className="list__item observacao">
                  <p>{obs.texto}</p>
                  <ul className="observacao__evidencias">
                    {obs.evidencias.map((ev) => (
                      <li key={ev.segmento_id}>
                        <p className="meta">{formatTimestamp(ev.inicio_ms)}</p>
                        <blockquote>{ev.trecho}</blockquote>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h2>Matriz de transições</h2>
            <p>
              Quantas vezes a aula passou de uma categoria FIAS para outra, a cada três segundos. As categorias
              vão de 1 a 10: 1 a 4 são influência indireta do professor, 5 a 7 são influência direta, 8 e 9 são
              fala dos estudantes, e 10 é silêncio ou confusão.
            </p>
            {/* Uma matriz 10x10 mede 400px e não quebra em linha como o resto do
               produto: em 360px ela arrastava a PÁGINA INTEIRA para o lado — o
               título e a barra de navegação saíam da tela junto. Quem rola é a
               tabela, não a página. `tabIndex` porque uma área rolável precisa
               ser alcançável pelo teclado (WCAG 2.1.1); `role`/`aria-label`
               para ela se anunciar como região, e não como um bloco anônimo. */}
            <div className="tabela-rolante" tabIndex={0} role="region"
              aria-label="Matriz de transições FIAS, rolável na horizontal">
              <table className="table">
                <caption>Matriz de transições FIAS (10×10): categoria de origem (linha) para categoria seguinte (coluna).</caption>
                <thead>
                  <tr>
                    <th scope="col">De \ para</th>
                    {CATEGORIAS.map((c) => <th key={c} scope="col">{c}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {dados.matriz.map((linha, i) => (
                    <tr key={i + 1}>
                      <th scope="row">{i + 1}</th>
                      {linha.map((valor, j) => <td key={j + 1}>{valor}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section>
            <h2>Índices</h2>
            <ul className="list">
              {dados.indices.map((idx) => (
                <li key={idx.codigo} className="list__item indice">
                  <div>
                    <h3>{idx.nome}</h3>
                    <p>{idx.descricao}</p>
                  </div>
                  <p className="indice__valor">{formatValor(idx.valor)}</p>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </>
  );
}
