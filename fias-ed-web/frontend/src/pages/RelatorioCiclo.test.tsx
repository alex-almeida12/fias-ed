import { screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { jsonResponse, mockApi, PROFESSORA, renderApp } from "../test-utils";

const RELATORIO = "GET /api/ciclos/c1/relatorio";

const CICLO = {
  id: "c1", turma: { id: "t1", name: "9º B" }, disciplina: { id: "d1", name: "História" },
  n_aulas_previstas: 8, iniciado_em: "2026-03-01", encerrado_em: null,
};

function indices(valor: number | null = 0.5) {
  return [{ codigo: "TT", nome: "Fala docente", valor, descricao: "Proporção do tempo da aula ocupada pela fala do professor." }];
}

function aula(overrides: Record<string, unknown> = {}) {
  return { aula_id: "a1", lesson_date: "2026-03-02", status: "FIAS_COMPLETED", indices: indices(), ...overrides };
}

// Rótulos deliberadamente fictícios (não são os de qti_config.json de verdade):
// provam que a tela mostra o que a API mandou, não um texto próprio.
function octantes() {
  return [
    { octant: "oc1", label: "Rótulo simulado A", value: 4 },
    { octant: "oc2", label: "Rótulo simulado B", value: 3.5 },
  ];
}

function coleta(overrides: Record<string, unknown> = {}) {
  return {
    id: "col1", coletado_em: "2026-03-10", origem: "COLETA_NATIVA", response_count: 12,
    displayable: true, octantes: octantes(), ...overrides,
  };
}

function relatorio(overrides: Record<string, unknown> = {}) {
  return { ciclo: CICLO, n_aulas_realizadas: 1, trajetoria: [aula()], coletas: [coleta()], ...overrides };
}

function mockRelatorio(corpo: Record<string, unknown> = relatorio()) {
  return mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    [RELATORIO]: () => jsonResponse(corpo),
  });
}

test("a trajetória aparece na ordem recebida, uma linha por aula", async () => {
  mockRelatorio(relatorio({
    trajetoria: [
      aula({ aula_id: "a1", lesson_date: "2026-03-01" }),
      aula({ aula_id: "a2", lesson_date: "2026-03-08" }),
      aula({ aula_id: "a3", lesson_date: "2026-03-15" }),
    ],
  }));
  renderApp("/ciclos/c1/relatorio");
  await screen.findByText(/trajetória do ciclo/i);
  const linhas = screen.getAllByRole("row").slice(1); // primeira é o cabeçalho
  expect(linhas.map((l) => l.textContent)).toEqual([
    expect.stringContaining("01/03/2026"),
    expect.stringContaining("08/03/2026"),
    expect.stringContaining("15/03/2026"),
  ]);
});

test("as coletas aparecem, com a data e a contagem de respostas", async () => {
  mockRelatorio(relatorio({ coletas: [coleta({ coletado_em: "2026-03-12", response_count: 27 })] }));
  renderApp("/ciclos/c1/relatorio");
  expect(await screen.findByText(/12\/03\/2026/)).toBeInTheDocument();
  expect(screen.getByText(/27 respostas/)).toBeInTheDocument();
});

test("nenhum texto de veredito aparece na tela", async () => {
  mockRelatorio();
  renderApp("/ciclos/c1/relatorio");
  await screen.findByText(/trajetória do ciclo/i);
  expect(document.body.textContent).not.toMatch(/melhor|pior|evolu|progress|regred|avalia|nota|desempenho|ranking/i);
});

test("aula sem índices aparece na tabela, marcada como ainda sem análise", async () => {
  mockRelatorio(relatorio({
    trajetoria: [
      aula({ aula_id: "a1", lesson_date: "2026-03-01" }),
      aula({ aula_id: "a2", lesson_date: "2026-03-08", status: "DRAFT", indices: [] }),
    ],
  }));
  renderApp("/ciclos/c1/relatorio");
  await screen.findByText(/trajetória do ciclo/i);
  expect(screen.getByText(/ainda sem análise/i)).toBeInTheDocument();
});

test("índice com valor null não vira zero nem célula vazia", async () => {
  mockRelatorio(relatorio({ trajetoria: [aula({ indices: indices(null) })] }));
  renderApp("/ciclos/c1/relatorio");
  expect(await screen.findByText(/sem trechos suficientes nesta aula para calcular/i)).toBeInTheDocument();
});

test("coleta com displayable false mostra a contagem e não mostra octantes", async () => {
  mockRelatorio(relatorio({
    coletas: [coleta({ displayable: false, response_count: 3 })],
  }));
  renderApp("/ciclos/c1/relatorio");
  expect(await screen.findByText(/3 respostas/)).toBeInTheDocument();
  expect(screen.queryByText(/rótulo simulado/i)).not.toBeInTheDocument();
});

test("o rótulo do octante é o que a API mandou, não um mapa fixo na tela", async () => {
  // "oc9" não existe em qti_config.json de verdade — se a tela tivesse seu
  // próprio mapa código→rótulo copiado de lá, esse código não constaria nele
  // e o rótulo fictício abaixo não apareceria como veio.
  mockRelatorio(relatorio({
    coletas: [coleta({ octantes: [{ octant: "oc9", label: "Rótulo Fictício Só Para Este Teste", value: 2 }] })],
  }));
  renderApp("/ciclos/c1/relatorio");
  expect(await screen.findByText(/rótulo fictício só para este teste/i)).toBeInTheDocument();
});

test("ciclo em andamento não mostra data vazia", async () => {
  mockRelatorio(relatorio({ ciclo: { ...CICLO, encerrado_em: null } }));
  renderApp("/ciclos/c1/relatorio");
  expect(await screen.findByText(/em andamento/i)).toBeInTheDocument();
});

test("nenhuma aula do ciclo foi classificada ainda: a tabela só tem Data e Situação", async () => {
  mockRelatorio(relatorio({
    trajetoria: [
      aula({ aula_id: "a1", lesson_date: "2026-03-01", status: "DRAFT", indices: [] }),
      aula({ aula_id: "a2", lesson_date: "2026-03-08", status: "AUDIO_IMPORTED", indices: [] }),
    ],
  }));
  renderApp("/ciclos/c1/relatorio");
  await screen.findByText(/trajetória do ciclo/i);
  const cabecalhos = screen.getAllByRole("columnheader").map((th) => th.textContent);
  expect(cabecalhos).toEqual(["Data", "Situação"]);
});

test("sem coletas, a tela diz que a turma ainda não respondeu, sem role de alerta", async () => {
  mockRelatorio(relatorio({ coletas: [] }));
  renderApp("/ciclos/c1/relatorio");
  expect(await screen.findByText(/turma ainda não respondeu ao questionário/i)).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
