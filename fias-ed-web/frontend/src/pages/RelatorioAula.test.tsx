import { screen } from "@testing-library/react";
import { expect, test } from "vitest";
import type { QtiAgreement } from "../api/types";
import { jsonResponse, mockApi, PROFESSORA, renderApp } from "../test-utils";
import { textoConcordancia } from "./RelatorioAula";

const RELATORIO = "GET /api/aulas/a1/relatorio";

const AULA = {
  id: "a1", lesson_date: "2026-09-01", status: "REPORT_READY",
  turma: { id: "t1", name: "9º B" }, disciplina: { id: "d1", name: "História" },
  note: null, error_code: null, error_message: null, audio: null,
  upload_pendente: null, job_ativo: false, alterada_pelo_admin_em: null, acompanhamento: null,
};

function par(overrides: Record<string, unknown> = {}) {
  return {
    pair_id: "TRI_WARMTH",
    fias: { kind: "categories", ref: [2, 3], value: 0.4 },
    qti_values: [{ octant: "oc2", label: "Dominante cooperativo", value: 3.2 }],
    qti_available: true,
    reflection_question: "Pergunta de reflexão padrão",
    source_reference: "CAP4 subsec:art2-triangulacao",
    validation_status: "PENDING_SCIENTIFIC_VALIDATION",
    ...overrides,
  };
}

// Sempre 4 pares (garantia da rota, Task 10) — cada um com uma pergunta de
// reflexão distinta para os testes poderem contar quantas apareceram.
function quatroPares(overrides: Array<Record<string, unknown>> = []) {
  const ids = ["TRI_WARMTH", "TRI_STRICT", "TRI_UNDERSTANDING", "TRI_STUDENT_FREEDOM"];
  return ids.map((pair_id, i) => par({
    pair_id, reflection_question: `Pergunta de reflexão ${i + 1}`, ...(overrides[i] ?? {}),
  }));
}

function interpretacao(overrides: Record<string, unknown> = {}) {
  return {
    rule_id: "MTSS_EXPOSITIVE_PREDOMINANCE",
    tier1_dimension: "Ensino explícito (modelagem)",
    framing: "reflection",
    interpretation: "A exposição foi o tipo de fala docente mais frequente nesta aula.",
    evidence: {},
    evidence_segment_categories: [5],
    source_reference: "CAP4 tab:art2-fias-tier1",
    validation_status: "PENDING_SCIENTIFIC_VALIDATION",
    rules_version: "1.1.0",
    qti_agreement: "unpaired",
    qti_evidence: null,
    divergence_question: null,
    evidencias: [{ segmento_id: "s1", inicio_ms: 1000, trecho: "vamos começar a explicar a questão" }],
    ...overrides,
  };
}

function recomendacao(overrides: Record<string, unknown> = {}) {
  return {
    recommendation_id: "PED_CHECK_UNDERSTANDING",
    rule_id: "MTSS_EXPOSITIVE_PREDOMINANCE",
    text: "Considere intercalar os momentos de exposição com pausas curtas.",
    validation_status: "draft_pending_researcher_review",
    source_reference: "CAP4 tab:art2-fias-tier1",
    qti_agreement: "unpaired",
    ...overrides,
  };
}

function relatorio(overrides: Record<string, unknown> = {}) {
  return {
    aula: AULA,
    indices: [{ codigo: "TT", nome: "Fala docente", valor: 0.5,
      descricao: "Proporção do tempo da aula ocupada pela fala do professor." }],
    triangulacao: quatroPares(),
    interpretacoes: [interpretacao()],
    recomendacoes: [recomendacao()],
    ...overrides,
  };
}

function mockRelatorio(corpo: Record<string, unknown> = relatorio()) {
  return mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    [RELATORIO]: () => jsonResponse(corpo),
  });
}

test("o relatório completo aparece: índices, os quatro pares e as recomendações", async () => {
  mockRelatorio();
  renderApp("/aulas/a1/relatorio");
  expect(await screen.findByRole("heading", { name: /fala docente/i, level: 3 })).toBeInTheDocument();
  expect(screen.getAllByText(/pergunta de reflexão/i)).toHaveLength(4);
  expect(screen.getByText(/considere intercalar/i)).toBeInTheDocument();
});

test("recomendações concordantes vêm primeiro, o resto na ordem em que veio", async () => {
  mockRelatorio(relatorio({
    recomendacoes: [
      recomendacao({ recommendation_id: "R1", text: "Recomendação sem QTI ainda.", qti_agreement: "no_qti" }),
      recomendacao({ recommendation_id: "R2", text: "Recomendação concordante com a turma.", qti_agreement: "agree" }),
      recomendacao({ recommendation_id: "R3", text: "Recomendação que diverge da turma.", qti_agreement: "disagree" }),
    ],
  }));
  renderApp("/aulas/a1/relatorio");
  await screen.findByText(/sugestões pedagógicas/i);
  // Ordem dos elementos no documento, não a ordem do JSON enviado pela API.
  const itens = screen.getAllByText(/^Recomendação (sem QTI|concordante|que diverge)/);
  expect(itens[0]).toHaveTextContent(/concordante/i);
});

test("divergência mostra a pergunta de divergência", async () => {
  mockRelatorio(relatorio({
    interpretacoes: [interpretacao({
      qti_agreement: "disagree",
      divergence_question: "O áudio registra pouco elogio verbal; o que mais pode explicar essa diferença?",
    })],
  }));
  renderApp("/aulas/a1/relatorio");
  expect(await screen.findByText(/o que mais pode explicar essa diferença/i)).toBeInTheDocument();
});

test("sem questionário, a pergunta de reflexão continua aparecendo", async () => {
  mockRelatorio(relatorio({
    triangulacao: quatroPares([
      { qti_available: false }, { qti_available: false }, { qti_available: false }, { qti_available: false },
    ]),
  }));
  renderApp("/aulas/a1/relatorio");
  expect(await screen.findAllByText(/turma ainda não respondeu ao questionário/i)).toHaveLength(4);
  expect(screen.getAllByText(/pergunta de reflexão/i)).toHaveLength(4);
  // A ausência de resposta não é um erro: nenhum banner desse aviso vira alerta.
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

test("recomendação sem par de triangulação não parece erro", async () => {
  mockRelatorio(relatorio({
    recomendacoes: [recomendacao({ text: "Recomendação isolada, sem par de triangulação.", qti_agreement: "unpaired" })],
  }));
  renderApp("/aulas/a1/relatorio");
  await screen.findByText(/recomendação isolada/i);
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  // Não basta não ser alerta: o texto ao lado tem que ser o de "unpaired", não
  // um genérico que colapsaria os cinco estados numa única mensagem.
  expect(screen.getByText(textoConcordancia("unpaired", "Esta recomendação"))).toBeInTheDocument();
});

test("cada um dos cinco estados de concordância mostra o texto correspondente, não um genérico", async () => {
  // achado da revisão: os 7 testes anteriores passavam mesmo com as cinco
  // mensagens colapsadas numa string só ("Concordância registrada."), porque
  // nenhum comparava o texto exibido contra o que textoConcordancia devolve.
  const estados: QtiAgreement[] = ["agree", "disagree", "inconclusive", "unpaired", "no_qti"];
  mockRelatorio(relatorio({
    interpretacoes: estados.map((qti_agreement, i) => interpretacao({
      rule_id: `RULE_${i}`, tier1_dimension: `Dimensão ${i}`, qti_agreement,
      // divergence_question fora do escopo deste teste: já coberta em teste próprio.
      divergence_question: null,
    })),
  }));
  renderApp("/aulas/a1/relatorio");
  await screen.findByText(/dimensão 0/i);
  for (const estado of estados) {
    expect(screen.getByText(textoConcordancia(estado, "Esta interpretação"))).toBeInTheDocument();
  }
});

test("aula que ainda não chegou mostra a mensagem do servidor, não um texto genérico", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    [RELATORIO]: () => jsonResponse({ error_code: "AULA_STATE",
      message: "Esta aula está esperando o questionário (QTI) da turma antes de fechar o relatório." }, 409),
  });
  renderApp("/aulas/a1/relatorio");
  expect(await screen.findByRole("alert")).toHaveTextContent(/esperando o questionário/i);
});

test("a tela não usa vocabulário de veredito", async () => {
  mockRelatorio();
  renderApp("/aulas/a1/relatorio");
  await screen.findByRole("heading", { name: /fala docente/i, level: 3 });
  expect(document.body.textContent).not.toMatch(/avalia|nota do professor|desempenho|ranking/i);
});
