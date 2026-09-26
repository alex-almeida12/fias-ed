import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test } from "vitest";
import { jsonResponse, mockApi, renderApp } from "../test-utils";

const ABRIR = "GET /publico/qti/tok123";
const CONSENTIR = "POST /publico/qti/tok123/consentir";
// Achado desta tarefa: declarada no brief, mas nenhum dos 5 testes do Step 1 a
// usa (nenhum chega a enviar as 24 respostas) — sem o disable, `npm run lint`
// falha com "'RESPONDER' is assigned a value but never used".
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const RESPONDER = "POST /publico/qti/tok123/responder";

const ITENS = Array.from({ length: 24 }, (_, i) => ({ order: i + 1, text: `pergunta ${i + 1}` }));
const ESCALA = { min: 1, max: 5, min_label: "(Quase) nunca", max_label: "(Quase) sempre" };
const QUESTIONARIO = { stem: "Este(a) professor(a)…", itens: ITENS, escala: ESCALA };

beforeEach(() => localStorage.clear());

test("o estudante consente antes de ver as perguntas", async () => {
  mockApi({ [ABRIR]: () => jsonResponse(QUESTIONARIO) });
  renderApp("/responder/tok123");
  expect(await screen.findByRole("button", { name: /concordo/i })).toBeInTheDocument();
  expect(screen.queryByText(/pergunta 1$/)).not.toBeInTheDocument();
});

test("a tela do estudante não exige login nem mostra o menu", async () => {
  mockApi({ [ABRIR]: () => jsonResponse(QUESTIONARIO) });
  renderApp("/responder/tok123");
  await screen.findByRole("button", { name: /concordo/i });
  expect(screen.queryByRole("link", { name: /minhas aulas/i })).not.toBeInTheDocument();
});

test("link fora de validade mostra a mensagem do servidor, sem formulário", async () => {
  mockApi({ [ABRIR]: () => jsonResponse(
    { error_code: "LINK_INVALIDO", message: "Este link não está mais disponível." }, 404) });
  renderApp("/responder/tok123");
  expect(await screen.findByText(/não está mais disponível/i)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /concordo/i })).not.toBeInTheDocument();
});

test("quem já respondeu neste navegador vê o agradecimento, não o formulário", async () => {
  localStorage.setItem("fias-ed:respondido:tok123", "1");
  mockApi({ [ABRIR]: () => jsonResponse(QUESTIONARIO) });
  renderApp("/responder/tok123");
  expect(await screen.findByText(/já respondeu/i)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /concordo/i })).not.toBeInTheDocument();
});

test("enviar só é possível com as 24 respondidas", async () => {
  mockApi({ [ABRIR]: () => jsonResponse(QUESTIONARIO),
            [CONSENTIR]: () => jsonResponse({}, 201) });
  renderApp("/responder/tok123");
  await userEvent.click(await screen.findByRole("button", { name: /concordo/i }));
  await screen.findByText(/pergunta 1$/);
  expect(screen.getByRole("button", { name: /enviar/i })).toBeDisabled();
});
