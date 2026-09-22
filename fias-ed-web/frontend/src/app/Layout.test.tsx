import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { ADMIN, jsonResponse, mockApi, PROFESSORA, renderApp } from "../test-utils";

test("professor não vê links de administração", async () => {
  mockApi({ "GET /api/auth/me": () => jsonResponse(PROFESSORA), "GET /api/aulas": () => jsonResponse([]) });
  renderApp("/aulas");
  expect(await screen.findByRole("link", { name: "Minhas aulas" })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Contas" })).not.toBeInTheDocument();
});

test("admin vê links de administração", async () => {
  mockApi({ "GET /api/auth/me": () => jsonResponse(ADMIN), "GET /api/aulas": () => jsonResponse([]) });
  renderApp("/aulas");
  expect(await screen.findByRole("link", { name: "Contas" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Aulas dos professores" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Escolas" })).toBeInTheDocument();
});

test("faixa 'agindo como' e volta à própria conta", async () => {
  const acting = { ...ADMIN, acting_as: { id: "p1", display_name: "Ana Souza" } };
  mockApi({
    "GET /api/auth/me": () => jsonResponse(acting),
    "GET /api/aulas": () => jsonResponse([]),
    "DELETE /api/admin/agir-como": () => jsonResponse(ADMIN),
    "GET /api/admin/aulas": () => jsonResponse([]),
    "GET /api/admin/contas": () => jsonResponse([]),
  });
  renderApp("/aulas");
  expect(await screen.findByText("Você está agindo como: Ana Souza")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Voltar à minha conta" }));
  await waitFor(() => expect(screen.queryByText(/Você está agindo como/)).not.toBeInTheDocument());
});

test("sair encerra a sessão", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas": () => jsonResponse([]),
    "POST /api/auth/logout": () => jsonResponse(null, 204),
  });
  renderApp("/aulas");
  await userEvent.click(await screen.findByRole("button", { name: "Sair" }));
  await waitFor(() => expect(window.location.pathname).toBe("/"));
});

// Ruling P15: sair/voltar não devem falhar silenciosamente.
test("erro ao sair mostra aviso e mantém a sessão", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas": () => jsonResponse([]),
    "POST /api/auth/logout": () => jsonResponse({ error_code: "ERRO", message: "Não foi possível sair." }, 500),
  });
  renderApp("/aulas");
  await userEvent.click(await screen.findByRole("button", { name: "Sair" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível sair.");
  expect(window.location.pathname).toBe("/aulas");
});

test("erro ao voltar à própria conta mostra aviso", async () => {
  const acting = { ...ADMIN, acting_as: { id: "p1", display_name: "Ana Souza" } };
  mockApi({
    "GET /api/auth/me": () => jsonResponse(acting),
    "GET /api/aulas": () => jsonResponse([]),
    "DELETE /api/admin/agir-como": () => jsonResponse({ error_code: "ERRO", message: "Não foi possível voltar." }, 500),
  });
  renderApp("/aulas");
  await userEvent.click(await screen.findByRole("button", { name: "Voltar à minha conta" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível voltar.");
  expect(screen.getByText("Você está agindo como: Ana Souza")).toBeInTheDocument();
});

test("sessão expirada: 401 numa chamada leva à entrada com aviso", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas": () => jsonResponse({ error_code: "UNAUTHENTICATED", message: "Entre com seu usuário e senha." }, 401),
  });
  renderApp("/aulas");
  await waitFor(() => expect(window.location.pathname).toBe("/"));
  expect(await screen.findByRole("heading", { name: "Entrar" })).toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("Sua sessão terminou. Entre de novo com seu usuário e senha.");
  expect(screen.queryByRole("button", { name: "Sair" })).not.toBeInTheDocument();
});

test("sair com a sessão já expirada (401) conta como saída", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas": () => jsonResponse([]),
    "POST /api/auth/logout": () => jsonResponse({ error_code: "UNAUTHENTICATED", message: "Entre com seu usuário e senha." }, 401),
  });
  renderApp("/aulas");
  await userEvent.click(await screen.findByRole("button", { name: "Sair" }));
  await waitFor(() => expect(window.location.pathname).toBe("/"));
  expect(await screen.findByRole("heading", { name: "Entrar" })).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
