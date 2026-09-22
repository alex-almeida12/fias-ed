import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { jsonResponse, mockApi, PROFESSORA, renderApp } from "../test-utils";

const unauth = () => jsonResponse({ error_code: "UNAUTHENTICATED", message: "Entre com seu usuário e senha." }, 401);

test("mostra a mensagem principal e o formulário de entrada", async () => {
  mockApi({ "GET /api/auth/me": unauth });
  renderApp("/");
  expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("Grave sua aula.Melhore sua prática docente.");
  expect(screen.getByText("Envie o áudio de uma aula e conheça melhor os padrões de interação que acontecem em sala.")).toBeInTheDocument();
  expect(screen.getByLabelText("Usuário")).toBeInTheDocument();
});

test("entrar leva às aulas", async () => {
  mockApi({
    "GET /api/auth/me": unauth,
    "POST /api/auth/login": () => jsonResponse(PROFESSORA),
    "GET /api/aulas": () => jsonResponse([]),
  });
  renderApp("/");
  await userEvent.type(await screen.findByLabelText("Usuário"), "ana");
  await userEvent.type(screen.getByLabelText("Senha"), "senha-de-teste-123");
  await userEvent.click(screen.getByRole("button", { name: "Entrar" }));
  await waitFor(() => expect(window.location.pathname).toBe("/aulas"));
  // `findBy` e não `getBy`: a URL muda assim que o navigate() roda, mas o React pode
  // ainda não ter recommitado a árvore com o Layout. Com getBy, este teste falhava
  // em ~1 de cada 5 execuções.
  expect(await screen.findByRole("link", { name: "Minhas aulas" })).toBeInTheDocument();
});

test("falha de login mostra a mensagem da API", async () => {
  mockApi({
    "GET /api/auth/me": unauth,
    "POST /api/auth/login": () => jsonResponse({ error_code: "LOGIN_FAILED", message: "Usuário ou senha incorretos." }, 401),
  });
  renderApp("/");
  await userEvent.type(await screen.findByLabelText("Usuário"), "ana");
  await userEvent.type(screen.getByLabelText("Senha"), "errada");
  await userEvent.click(screen.getByRole("button", { name: "Entrar" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Usuário ou senha incorretos.");
});

test("senha provisória obriga a troca", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse({ ...PROFESSORA, must_change_password: true }),
    "POST /api/auth/password": () => jsonResponse(PROFESSORA),
    "GET /api/aulas": () => jsonResponse([]),
  });
  renderApp("/aulas");
  expect(await screen.findByRole("heading", { name: "Troque sua senha" })).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Senha atual"), "provisoria-123");
  await userEvent.type(screen.getByLabelText("Nova senha"), "curta");
  await userEvent.type(screen.getByLabelText("Repita a nova senha"), "curta");
  await userEvent.click(screen.getByRole("button", { name: "Salvar nova senha" }));
  expect(await screen.findByText("A senha precisa ter pelo menos 12 caracteres.")).toBeInTheDocument();
  await userEvent.clear(screen.getByLabelText("Nova senha"));
  await userEvent.type(screen.getByLabelText("Nova senha"), "minha-senha-nova-1");
  await userEvent.clear(screen.getByLabelText("Repita a nova senha"));
  await userEvent.type(screen.getByLabelText("Repita a nova senha"), "minha-senha-nova-1");
  await userEvent.click(screen.getByRole("button", { name: "Salvar nova senha" }));
  await waitFor(() => expect(window.location.pathname).toBe("/aulas"));
});
