import { screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { jsonResponse, mockApi, PROFESSORA, renderApp } from "../test-utils";

const ACOMPANHAMENTO = {
  id: "c1", turma: { id: "t1", name: "9º B" }, disciplina: { id: "d1", name: "História" },
  n_aulas_previstas: 8, iniciado_em: "2026-03-01", encerrado_em: null,
};

test("a lista aparece com turma e disciplina de cada acompanhamento", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/ciclos": () => jsonResponse([ACOMPANHAMENTO]),
  });
  renderApp("/ciclos");
  expect(await screen.findByText("9º B · História")).toBeInTheDocument();
});

test("cada acompanhamento tem os dois caminhos, com os endereços certos", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/ciclos": () => jsonResponse([ACOMPANHAMENTO]),
  });
  renderApp("/ciclos");
  expect(await screen.findByRole("link", { name: "Ver o acompanhamento" })).toHaveAttribute("href", "/ciclos/c1/relatorio");
  expect(screen.getByRole("link", { name: "Enviar o relatório do questionário" })).toHaveAttribute("href", "/ciclos/c1/qti");
});

test("sem acompanhamentos, a tela explica e oferece começar, sem alerta de erro", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/ciclos": () => jsonResponse([]),
  });
  renderApp("/ciclos");
  expect(await screen.findByText("Nenhum acompanhamento ainda")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Começar um acompanhamento" })).toHaveAttribute("href", "/ciclos/novo");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

test("o menu tem a entrada 'Meus acompanhamentos' apontando para /ciclos", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/ciclos": () => jsonResponse([]),
  });
  renderApp("/ciclos");
  expect(await screen.findByRole("link", { name: "Meus acompanhamentos" })).toHaveAttribute("href", "/ciclos");
});

test("a tela não usa a palavra 'ciclo' nem vocabulário de avaliação", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/ciclos": () => jsonResponse([ACOMPANHAMENTO]),
  });
  renderApp("/ciclos");
  await screen.findByText("9º B · História");
  expect(document.body.textContent).not.toMatch(/ciclo/i);
  expect(document.body.textContent).not.toMatch(/avalia|nota|desempenho|ranking/i);
});
