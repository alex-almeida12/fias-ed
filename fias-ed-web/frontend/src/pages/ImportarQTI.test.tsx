import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { jsonResponse, mockApi, PROFESSORA, renderApp } from "../test-utils";

const IMPORTAR = "POST /api/ciclos/c1/qti/importar";
const OK = { id: "k1", coletado_em: "2026-09-20", origem: "IMPORTACAO_EXTERNA",
  response_count: 12, displayable: true, min_responses: 10 };

function arquivo() {
  return new File(["q1,q2\n4,5\n"], "relatorio.csv", { type: "text/csv" });
}

async function preencherEEnviar() {
  renderApp("/ciclos/c1/qti");
  await userEvent.upload(await screen.findByLabelText(/relatório/i), arquivo());
  await userEvent.type(screen.getByLabelText(/quando a turma respondeu/i), "2026-09-20");
  await userEvent.click(screen.getByRole("button", { name: /enviar/i }));
}

test("importar um relatório válido mostra quantas respostas entraram", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    [IMPORTAR]: () => jsonResponse(OK, 201),
  });
  await preencherEEnviar();
  expect(await screen.findByText(/12 respostas/i)).toBeInTheDocument();
});

test("a data em que a turma respondeu é enviada junto", async () => {
  const spy = mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    [IMPORTAR]: () => jsonResponse(OK, 201),
  });
  await preencherEEnviar();
  const post = spy.mock.calls.find(([, init]) => init?.method === "POST");
  const corpo = post![1]!.body as FormData;
  expect(corpo.get("coletado_em")).toBe("2026-09-20");
  expect((corpo.get("arquivo") as File).name).toBe("relatorio.csv");
});

test("arquivo recusado mostra a mensagem do servidor e mantém a saída", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    [IMPORTAR]: () => jsonResponse({ error_code: "QTI_IMPORT_INVALIDO",
      message: "Linha 4: item 3 fora da escala 1–5." }, 422),
  });
  await preencherEEnviar();
  expect(await screen.findByRole("alert")).toHaveTextContent(/linha 4/i);
  // A saída continua aberta: o professor corrige o arquivo e tenta de novo
  // sem perder a tela.
  expect(screen.getByLabelText(/relatório/i)).toBeInTheDocument();
});

test("poucas respostas avisa sem tratar como erro", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    [IMPORTAR]: () => jsonResponse({ ...OK, response_count: 4, displayable: false }, 201),
  });
  await preencherEEnviar();
  expect(await screen.findByText(/pelo menos 10/i)).toBeInTheDocument();
  // Importou: não é erro. Só não dá para mostrar o resultado ainda.
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

test("a tela não usa vocabulário de avaliação", async () => {
  mockApi({ "GET /api/auth/me": () => jsonResponse(PROFESSORA) });
  renderApp("/ciclos/c1/qti");
  // A asserção de ausência só vale depois da de presença: prova que carregou.
  await screen.findByLabelText(/relatório/i);
  expect(document.body.textContent).not.toMatch(/avalia|nota|desempenho|ranking/i);
});
