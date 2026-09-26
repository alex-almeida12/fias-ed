import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

test("mostra 'Em andamento' para o que não encerrou, a data para o que encerrou, e as aulas previstas", async () => {
  const emAndamento = ACOMPANHAMENTO;
  const encerrado = { ...ACOMPANHAMENTO, id: "c2", turma: { id: "t2", name: "8º A" },
    n_aulas_previstas: 5, encerrado_em: "2026-07-15" };
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/ciclos": () => jsonResponse([emAndamento, encerrado]),
  });
  renderApp("/ciclos");
  await screen.findByText("9º B · História");
  expect(screen.getByText(/Em andamento/)).toBeInTheDocument();
  expect(screen.getByText(/Encerrado em 15\/07\/2026/)).toBeInTheDocument();
  expect(screen.getByText(/8 aulas previstas/)).toBeInTheDocument();
  expect(screen.getByText(/5 aulas previstas/)).toBeInTheDocument();
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

test("acompanhamento em andamento mostra a ação de encerrar", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/ciclos": () => jsonResponse([ACOMPANHAMENTO]),
  });
  renderApp("/ciclos");
  expect(await screen.findByRole("button", { name: "Encerrar acompanhamento" })).toBeInTheDocument();
});

test("acompanhamento encerrado não mostra a ação de encerrar, e mostra a data", async () => {
  const encerrado = { ...ACOMPANHAMENTO, encerrado_em: "2026-07-15" };
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/ciclos": () => jsonResponse([encerrado]),
  });
  renderApp("/ciclos");
  expect(await screen.findByText(/Encerrado em 15\/07\/2026/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Encerrar acompanhamento" })).not.toBeInTheDocument();
});

test("confirmar o encerramento chama POST /api/ciclos/{id}/encerrar com o id certo", async () => {
  const spy = mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/ciclos": () => jsonResponse([ACOMPANHAMENTO]),
    "POST /api/ciclos/c1/encerrar": () => jsonResponse({}),
  });
  renderApp("/ciclos");
  await userEvent.click(await screen.findByRole("button", { name: "Encerrar acompanhamento" }));
  await userEvent.click(await screen.findByRole("button", { name: "Confirmar encerramento" }));
  await screen.findByRole("button", { name: "Encerrar acompanhamento" }); // dialog fechou e a lista recarregou
  expect(spy.mock.calls.some(([url, init]) => url === "/api/ciclos/c1/encerrar" && init?.method === "POST")).toBe(true);
});

test("cancelar a confirmação não chama a rota de encerrar", async () => {
  const spy = mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/ciclos": () => jsonResponse([ACOMPANHAMENTO]),
  });
  renderApp("/ciclos");
  await userEvent.click(await screen.findByRole("button", { name: "Encerrar acompanhamento" }));
  await userEvent.click(await screen.findByRole("button", { name: "Cancelar" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(spy.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
});

test("depois de encerrar, a lista reflete o novo estado sem recarregar a página", async () => {
  let encerrado = false;
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/ciclos": () => jsonResponse([{ ...ACOMPANHAMENTO, encerrado_em: encerrado ? "2026-09-25" : null }]),
    "POST /api/ciclos/c1/encerrar": () => { encerrado = true; return jsonResponse({}); },
  });
  renderApp("/ciclos");
  await userEvent.click(await screen.findByRole("button", { name: "Encerrar acompanhamento" }));
  await userEvent.click(await screen.findByRole("button", { name: "Confirmar encerramento" }));
  expect(await screen.findByText(/Encerrado em 25\/09\/2026/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Encerrar acompanhamento" })).not.toBeInTheDocument();
});

test("falha ao encerrar mostra a mensagem do servidor, e o acompanhamento continua na lista", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/ciclos": () => jsonResponse([ACOMPANHAMENTO]),
    "POST /api/ciclos/c1/encerrar": () => jsonResponse({ error_code: "ERRO_ENCERRAR", message: "Não foi possível encerrar agora." }, 500),
  });
  renderApp("/ciclos");
  await userEvent.click(await screen.findByRole("button", { name: "Encerrar acompanhamento" }));
  await userEvent.click(await screen.findByRole("button", { name: "Confirmar encerramento" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível encerrar agora.");
  expect(screen.getByText(/Em andamento/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Encerrar acompanhamento" })).toBeInTheDocument();
});
