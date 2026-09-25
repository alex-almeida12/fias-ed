import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router";
import { api, ApiError } from "../api/client";
import type { InterpretacaoMTSS, QtiAgreement, RecomendacaoMTSS, Relatorio } from "../api/types";
import { formatDate, formatTimestamp } from "../app/format";
import { Banner } from "../design/components/Banner";

function formatIndiceValor(valor: number | null): string {
  if (valor === null) return "Sem trechos suficientes nesta aula para calcular.";
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(valor);
}

function formatNumero(valor: number | null): string {
  if (valor === null) return "não calculado";
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(valor);
}

// Cada valor de qti_agreement significa algo diferente para o professor (brief
// da Task 11, tabela "cada estado precisa ser legível"). `unpaired` e `no_qti`
// não são falha: são leitura normal quando não há par de triangulação ou
// quando a turma ainda não respondeu ao questionário.
function textoConcordancia(valor: QtiAgreement, sujeito: string): string {
  switch (valor) {
    case "agree": return "As duas evidências apontam na mesma direção.";
    case "disagree": return "As duas evidências divergem.";
    case "inconclusive": return "A percepção da turma ficou na faixa intermediária.";
    case "unpaired": return `${sujeito} se apoia só na observação da aula.`;
    case "no_qti": return "A turma ainda não respondeu ao questionário.";
  }
}

// Decisão do pesquisador (Task 11): as recomendações concordantes vêm primeiro.
// A rota devolve na ordem em que o motor gravou, de propósito (comentário em
// app/relatorios/routes.py) — é aqui, na apresentação, que a ordenação existe.
// O resto da lista mantém a ordem recebida; nada além de "agree" é reordenado.
function ordenarRecomendacoes(recomendacoes: RecomendacaoMTSS[]): RecomendacaoMTSS[] {
  const concordantes = recomendacoes.filter((r) => r.qti_agreement === "agree");
  const resto = recomendacoes.filter((r) => r.qti_agreement !== "agree");
  return [...concordantes, ...resto];
}

function Interpretacao({ item }: { item: InterpretacaoMTSS }) {
  return (
    <li className="list__item observacao">
      <h3>{item.tier1_dimension}</h3>
      <p>{item.interpretation}</p>
      {item.evidencias.length > 0 && (
        <ul className="observacao__evidencias">
          {item.evidencias.map((ev) => (
            <li key={ev.segmento_id}>
              <p className="meta">{formatTimestamp(ev.inicio_ms)}</p>
              <blockquote>{ev.trecho}</blockquote>
            </li>
          ))}
        </ul>
      )}
      <p className="meta">{textoConcordancia(item.qti_agreement, "Esta interpretação")}</p>
      {item.qti_agreement === "disagree" && item.divergence_question && <p>{item.divergence_question}</p>}
    </li>
  );
}

export function RelatorioAula() {
  const { id = "" } = useParams();
  const [dados, setDados] = useState<Relatorio | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    try {
      const resposta = await api<Relatorio>(`/aulas/${id}/relatorio`);
      setDados(resposta);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Não foi possível carregar o relatório desta aula.");
    }
  }, [id]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  return (
    <>
      <h1>Relatório da aula</h1>
      {erro && <Banner kind="error">{erro}</Banner>}
      {dados === null && !erro && <p role="status">Carregando…</p>}

      {dados && (
        <>
          <p className="meta">
            {formatDate(dados.aula.lesson_date)} · {dados.aula.turma.name} · {dados.aula.disciplina.name}
          </p>

          <section>
            <h2>O que a observação mediu</h2>
            <ul className="list">
              {dados.indices.map((idx) => (
                <li key={idx.codigo} className="list__item indice">
                  <div>
                    <h3>{idx.nome}</h3>
                    <p>{idx.descricao}</p>
                  </div>
                  <p className="indice__valor">{formatIndiceValor(idx.valor)}</p>
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h2>Como isso se compara à percepção dos estudantes</h2>
            <ul className="list">
              {dados.triangulacao.map((par) => (
                <li key={par.pair_id} className="list__item observacao">
                  <p className="meta">Medição da aula: {formatNumero(par.fias.value)}</p>
                  {par.qti_available ? (
                    <ul>
                      {par.qti_values.map((q) => (
                        <li key={q.octant}>{q.label}: {formatNumero(q.value)}</li>
                      ))}
                    </ul>
                  ) : (
                    <Banner>A turma ainda não respondeu ao questionário.</Banner>
                  )}
                  <p>{par.reflection_question}</p>
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h2>Interpretações da aula</h2>
            <ul className="list">
              {dados.interpretacoes.map((item) => <Interpretacao key={item.rule_id} item={item} />)}
            </ul>
          </section>

          <section>
            <h2>Sugestões pedagógicas</h2>
            <p className="meta">
              Estas sugestões ainda não foram revisadas pelo pesquisador — são rascunho, um degrau
              abaixo dos pares de triangulação acima.
            </p>
            <ul className="list">
              {ordenarRecomendacoes(dados.recomendacoes).map((rec) => (
                <li key={rec.recommendation_id} className="list__item observacao">
                  <p>{rec.text}</p>
                  <p className="meta">{textoConcordancia(rec.qti_agreement, "Esta recomendação")}</p>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </>
  );
}
