import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router";
import { api, ApiError } from "../api/client";
import type { Indice, InterpretacaoMTSS, QtiAgreement, RecomendacaoMTSS, Relatorio } from "../api/types";
import { formatDate, formatTimestamp } from "../app/format";
import { Banner } from "../design/components/Banner";

function formatIndiceValor(valor: number | null): string {
  if (valor === null) return "Sem trechos suficientes nesta aula para calcular.";
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(valor);
}

// Cartão do índice (Task 19, brief): TT/PT/SC/PIR/PUPIL_RESPONSE_RATIO são
// proporções de 0 a 1 — formatadas como porcentagem inteira. ID_RATIO é uma
// razão (quantas vezes um tipo de influência aparece para cada uma do outro),
// não uma fração de 0 a 1: levar o "%" para ele inventaria um significado que
// o número não tem. `valor: null` nunca vira "0%" — usa o mesmo texto que a
// tela já mostra hoje para "não deu para calcular".
function formatCartaoValor(idx: Indice): string {
  if (idx.valor === null || idx.codigo === "ID_RATIO") return formatIndiceValor(idx.valor);
  return `${Math.round(idx.valor * 100)}%`;
}

function formatNumero(valor: number | null): string {
  if (valor === null) return "não calculado";
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(valor);
}

// Cada valor de qti_agreement significa algo diferente para o professor (brief
// da Task 11, tabela "cada estado precisa ser legível"). `unpaired` e `no_qti`
// não são falha: são leitura normal quando não há par de triangulação ou
// quando a turma ainda não respondeu ao questionário.
export function textoConcordancia(valor: QtiAgreement, sujeito: string): string {
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

          {/* Bloco 1 — os cartões (brief da Task 19: "quem tem trinta segundos lê os
             cartões"). Nome, valor em destaque e um resumo curto por baixo — a
             descrição longa (`idx.descricao`) continua existindo no payload e
             continua sendo mostrada, só que na tela de padrões de interação
             (PadroesInteracao.tsx), não aqui: aqui não cabe uma frase inteira
             por cartão. Nenhuma cor semântica, nenhum ícone: o sistema descreve
             o número, não julga a aula. */}
          <section>
            <h2>O que a observação mediu</h2>
            <ul className="indices-cartoes">
              {dados.indices.map((idx) => (
                <li key={idx.codigo} className="indice-cartao">
                  <h3>{idx.nome}</h3>
                  <p className="indice-cartao__valor">{formatCartaoValor(idx)}</p>
                  <p className="indice-cartao__resumo">{idx.resumo}</p>
                </li>
              ))}
            </ul>
          </section>

          {/* Bloco 2 — a comparação com a percepção dos estudantes, como já funcionava. */}
          <section>
            <h2>Como isso se compara à percepção dos estudantes</h2>
            <ul className="list">
              {dados.triangulacao.map((par) => (
                <li key={par.pair_id} className="list__item observacao">
                  {/* A pergunta abre o item: ela nomeia o que está sendo comparado
                     (achado de usabilidade da revisão da Task 11) — sem ela, o
                     professor lê um número antes de saber do que ele trata. */}
                  <p>{par.reflection_question}</p>
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
                </li>
              ))}
            </ul>
          </section>

          {/* Bloco 3 — a leitura pedagógica: interpretações e recomendações, no fim
             ("quem tem cinco minutos desce até as recomendações"). Nenhum cartão
             está ligado a uma interpretação específica: das seis regras do MTSS
             habilitadas, só MTSS_DIRECT_OVER_INDIRECT usa um índice (ID_RATIO) —
             as demais olham categorias de fala, e inventar uma correspondência
             cartão-a-regra para as outras cinco não teria base nenhuma. */}
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
