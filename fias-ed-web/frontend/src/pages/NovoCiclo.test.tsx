import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { jsonResponse, mockApi, PROFESSORA, renderApp } from "../test-utils";

const ESCOLA = { id: "e1", name: "Escola A", municipality: "Mossoró", region: "Nordeste" };
const TURMA = { id: "t1", name: "9º B", school_year: 2026, level: null, escola: ESCOLA };
const DISCIPLINA = { id: "d1", name: "História" };
const CICLO = { id: "c1", turma_id: "t1", disciplina_id: "d1", professor_id: "p1",
  n_aulas_previstas: 8, iniciado_em: "2026-09-24", encerrado_em: null };

test("o professor declara quantas aulas vai acompanhar", async () => {
  const spy = mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/turmas": () => jsonResponse([TURMA]),
    "GET /api/disciplinas": () => jsonResponse([DISCIPLINA]),
    "POST /api/ciclos": () => jsonResponse(CICLO, 201),
  });
  renderApp("/ciclos/novo");
  await screen.findByRole("option", { name: /9º B/ });
  await userEvent.selectOptions(screen.getByLabelText(/turma/i), "t1");
  await userEvent.selectOptions(screen.getByLabelText(/disciplina/i), "d1");
  await userEvent.clear(screen.getByLabelText(/quantas aulas/i));
  await userEvent.type(screen.getByLabelText(/quantas aulas/i), "8");
  await userEvent.click(screen.getByRole("button", { name: /começar/i }));
  await waitFor(() => {
    const post = spy.mock.calls.find(([, init]) => init?.method === "POST");
    expect(post).toBeDefined();
    expect(JSON.parse(String(post![1]!.body))).toMatchObject({ n_aulas_previstas: 8 });
  });
});

test("a tela não usa vocabulário de avaliação", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/turmas": () => jsonResponse([]),
    "GET /api/disciplinas": () => jsonResponse([]),
  });
  renderApp("/ciclos/novo");
  // A asserção de ausência só vale depois da de presença: prova que a página carregou.
  await screen.findByLabelText(/quantas aulas/i);
  expect(document.body.textContent).not.toMatch(/avalia|nota|desempenho|ranking/i);
});
