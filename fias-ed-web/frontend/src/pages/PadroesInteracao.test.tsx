import { screen, within } from "@testing-library/react";
import { expect, test } from "vitest";
import { jsonResponse, mockApi, PROFESSORA, renderApp } from "../test-utils";

function matrizVazia(): number[][] {
  return Array.from({ length: 10 }, () => Array.from({ length: 10 }, () => 0));
}

const MATRIZ = matrizVazia();
MATRIZ[4][7] = 3; // categoria 5 → categoria 8, só para provar que o valor chega intacto à célula certa

const PADROES = {
  faixa: [
    { inicio_ms: 0, fim_ms: 3000, grupo: "direta" as const },
    { inicio_ms: 3000, fim_ms: 6000, grupo: "estudante" as const },
  ],
  observacoes: [
    {
      texto: "O professor explicou o conteúdo diretamente.",
      evidencias: [{ segmento_id: "s1", inicio_ms: 0, trecho: "vamos começar a explicar a questão" }],
    },
    {
      texto: "Os estudantes responderam a uma pergunta ou instrução do professor.",
      evidencias: [{ segmento_id: "s2", inicio_ms: 3000, trecho: "o que vocês acham disso" }],
    },
  ],
  matriz: MATRIZ,
  indices: [
    { codigo: "TT", nome: "Fala docente", valor: 0.5, descricao: "Proporção do tempo da aula ocupada pela fala do professor." },
    { codigo: "PT", nome: "Fala discente", valor: 0.5, descricao: "Proporção do tempo da aula ocupada pela fala dos estudantes." },
  ],
};

const FAIXA_QUATRO_GRUPOS = [
  { inicio_ms: 0, fim_ms: 3000, grupo: "indireta" as const },
  { inicio_ms: 3000, fim_ms: 6000, grupo: "direta" as const },
  { inicio_ms: 6000, fim_ms: 9000, grupo: "estudante" as const },
  { inicio_ms: 9000, fim_ms: 12000, grupo: "silêncio" as const },
];

function mockPadrao(extra: Record<string, () => Response> = {}) {
  return mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas/a1/padroes": () => jsonResponse(PADROES),
    ...extra,
  });
}

test("a tela abre pela faixa de tempo e pelas observações", async () => {
  mockPadrao();
  renderApp("/aulas/a1/padroes");
  const titulos = await screen.findAllByRole("heading", { level: 2 });
  expect(titulos[0]).toHaveTextContent(/como a aula se distribuiu/i);
});

test("cada observação mostra o trecho que a sustenta", async () => {
  mockPadrao();
  renderApp("/aulas/a1/padroes");
  expect(await screen.findByText(/o que vocês acham disso/i)).toBeInTheDocument();
});

test("a matriz aparece como tabela, com cabeçalho de linha e de coluna", async () => {
  mockPadrao();
  renderApp("/aulas/a1/padroes");
  const tabela = await screen.findByRole("table", { name: /matriz de transições/i });
  expect(within(tabela).getAllByRole("columnheader")).toHaveLength(11);
  // A célula (linha 5, coluna 8) carrega o valor que a API mandou, não um
  // recálculo do front nem um valor genérico — prova que a tabela é dado, não
  // um mapa de calor decorativo (nenhuma cor por valor).
  const cabecalhoLinha5 = within(tabela).getByRole("rowheader", { name: "5" });
  const linhaCategoria5 = cabecalhoLinha5.closest("tr")!;
  expect(within(linhaCategoria5).getAllByRole("cell")[7]).toHaveTextContent("3");
});

test("nenhum índice aparece com veredito", async () => {
  mockPadrao();
  renderApp("/aulas/a1/padroes");
  await screen.findByRole("table", { name: /matriz de transições/i });
  expect(screen.queryByText(/abaixo do esperado|bom|ruim|meta/i)).not.toBeInTheDocument();
});

test("cada segmento da faixa tem contorno que contrasta com os vizinhos", async () => {
  // As quatro cores de grupo não se separam sozinhas: indireta x direta dá
  // 2,32:1 e estudante x silêncio dá 1,27:1, abaixo dos 3:1 do WCAG 1.4.11.
  mockPadrao({ "GET /api/aulas/a1/padroes": () => jsonResponse({ ...PADROES, faixa: FAIXA_QUATRO_GRUPOS }) });
  renderApp("/aulas/a1/padroes");
  const faixa = await screen.findByRole("img", { name: /distribuição da fala/i });
  const escuros = faixa.querySelectorAll('[data-grupo="direta"], [data-grupo="indireta"]');
  const claros = faixa.querySelectorAll('[data-grupo="estudante"], [data-grupo="silencio"]');
  expect(escuros.length + claros.length).toBeGreaterThan(0);
  escuros.forEach((s) => expect(s).toHaveAttribute("stroke", "var(--color-white)"));
  claros.forEach((s) => expect(s).toHaveAttribute("stroke", "var(--color-navy)"));
});

test("a faixa de tempo tem alternativa textual", async () => {
  // Cor não pode ser o único portador de significado (DESIGN.md).
  mockPadrao();
  renderApp("/aulas/a1/padroes");
  expect(await screen.findByRole("img", { name: /distribuição da fala ao longo da aula/i })).toBeInTheDocument();
});

// ---- Desconfiança do brief: os cinco testes acima já eram esperados passar
// de primeira porque eu mesmo escrevi a implementação a partir deles. Os dois
// abaixo cobrem o que o brief não pedia e que um mock "feliz" não provaria.

test("a alternativa textual da faixa descreve a distribuição em palavras, não só nomeia a cor", async () => {
  mockPadrao();
  renderApp("/aulas/a1/padroes");
  const grafico = await screen.findByRole("img", { name: /distribuição da fala ao longo da aula/i });
  // metade direta, metade estudante — a descrição tem que trazer os dois grupos e um percentual.
  expect(grafico.getAttribute("aria-label")).toMatch(/50%.*influência direta/i);
  expect(grafico.getAttribute("aria-label")).toMatch(/50%.*estudantes/i);
});

test("erro ao carregar mostra aviso em vez de tela em branco", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas/a1/padroes": () => jsonResponse({ error_code: "AULA_STATE",
      message: "Esta aula ainda não tem uma classificação para mostrar." }, 409),
  });
  renderApp("/aulas/a1/padroes");
  expect(await screen.findByRole("alert")).toHaveTextContent(/ainda não tem uma classificação/i);
});
