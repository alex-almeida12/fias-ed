import { screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { jsonResponse, mockApi, PROFESSORA, renderApp } from "../test-utils";

test("estado vazio convida a adicionar a primeira aula", async () => {
  mockApi({ "GET /api/auth/me": () => jsonResponse(PROFESSORA), "GET /api/aulas": () => jsonResponse([]) });
  renderApp("/aulas");
  expect(await screen.findByText("Nenhuma aula ainda")).toBeInTheDocument();
  expect(screen.getAllByRole("link", { name: "Adicionar aula" })[0]).toHaveAttribute("href", "/aulas/nova");
});

test("lista aulas com status humano", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas": () => jsonResponse([{ id: "a1", lesson_date: "2026-09-22", status: "AUDIO_VALIDATED",
      turma: { id: "t1", name: "9º B" }, disciplina: { id: "d1", name: "Ciências" } }]),
  });
  renderApp("/aulas");
  expect(await screen.findByRole("link", { name: /22\/09\/2026/ })).toHaveAttribute("href", "/aulas/a1");
  expect(screen.getByText("9º B · Ciências")).toBeInTheDocument();
  expect(screen.getByText("Áudio conferido")).toBeInTheDocument();
});

test("admin agindo como vê o nome do professor no título", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse({ ...PROFESSORA, role: "ADMIN_LOCAL", acting_as: { id: "p9", display_name: "Bia" } }),
    "GET /api/aulas": () => jsonResponse([]),
  });
  renderApp("/aulas");
  expect(await screen.findByRole("heading", { name: "Aulas de Bia" })).toBeInTheDocument();
});

// Ruling P10: nome com HTML embutido deve ser renderizado como texto literal, nunca como HTML.
test("nome de turma com HTML é renderizado como texto literal", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas": () => jsonResponse([{ id: "a1", lesson_date: "2026-09-22", status: "DRAFT",
      turma: { id: "t1", name: "<script>alert(1)</script>" }, disciplina: { id: "d1", name: "Ciências" } }]),
  });
  renderApp("/aulas");
  expect(await screen.findByText("<script>alert(1)</script> · Ciências")).toBeInTheDocument();
  expect(document.querySelector("script")).toBeNull();
});

// Ruling P15: erro ao carregar a lista de aulas não deve ficar silencioso.
test("erro ao carregar aulas mostra aviso", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas": () => jsonResponse({ error_code: "ERRO", message: "Falha ao listar." }, 500),
  });
  renderApp("/aulas");
  expect(await screen.findByRole("alert")).toHaveTextContent("Falha ao listar.");
});
