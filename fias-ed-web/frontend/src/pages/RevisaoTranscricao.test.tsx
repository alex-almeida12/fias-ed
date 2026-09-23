import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { jsonResponse, mockApi, PROFESSORA, renderApp } from "../test-utils";

const SEGMENTO_1 = { id: "s1", start_ms: 0, end_ms: 2000, texto: "bom dia, turma", papel: "PROFESSOR" as const,
  version: 1, revisado: false };

function bloco(segmentos = [SEGMENTO_1], numero = 0, total = 1) {
  return { bloco: numero, blocos: total, segmentos };
}

function mockPadrao(extra: Record<string, () => Response> = {}) {
  return mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas/a1/transcricao?bloco=0": () => jsonResponse(bloco()),
    ...extra,
  });
}

test("mostra os segmentos do bloco com horário, falante e texto", async () => {
  mockPadrao();
  renderApp("/aulas/a1/transcricao");
  expect(await screen.findByDisplayValue("bom dia, turma")).toBeInTheDocument();
  expect(screen.getByText("0:00")).toBeInTheDocument();
  // "falante": o controle de troca é um botão de dois estados com texto, não só cor.
  expect(screen.getByRole("button", { name: /você.*marcar como estudante/i })).toBeInTheDocument();
  // O rótulo do campo existe (para leitor de tela), mesmo que visualmente escondido.
  expect(screen.getByLabelText(/texto do trecho de 0:00/i)).toHaveValue("bom dia, turma");
});

test("não salva ao sair do campo sem alterar nada", async () => {
  // Complementa o teste do brief: focar e sair sem digitar nada não pode disparar PATCH —
  // senão rolar a tela ou clicar por engano já infla `Segmento.revisado`.
  const spy = mockPadrao();
  renderApp("/aulas/a1/transcricao");
  const campo = await screen.findByDisplayValue("bom dia, turma");
  campo.focus();
  await userEvent.tab();
  await waitFor(() => expect(spy.mock.calls.filter(([, i]) => i?.method === "PATCH")).toHaveLength(0));
});

test("salva ao sair do campo, não a cada tecla", async () => {
  const spy = mockPadrao({
    "PATCH /api/segmentos/s1": () => jsonResponse({ ...SEGMENTO_1, texto: "bom dia, pessoal", version: 2 }),
  });
  renderApp("/aulas/a1/transcricao");
  const campo = await screen.findByDisplayValue("bom dia, turma");
  await userEvent.clear(campo);
  await userEvent.type(campo, "bom dia, pessoal");
  expect(spy.mock.calls.filter(([, i]) => i?.method === "PATCH")).toHaveLength(0);
  await userEvent.tab();
  await waitFor(() => expect(spy.mock.calls.filter(([, i]) => i?.method === "PATCH")).toHaveLength(1));
  const patch = spy.mock.calls.find(([, i]) => i?.method === "PATCH");
  expect(JSON.parse(String(patch![1]!.body))).toEqual({ texto: "bom dia, pessoal", version: 1 });
});

test("anuncia quando um trecho é salvo", async () => {
  mockPadrao({
    "PATCH /api/segmentos/s1": () => jsonResponse({ ...SEGMENTO_1, texto: "bom dia, pessoal", version: 2 }),
  });
  renderApp("/aulas/a1/transcricao");
  const campo = await screen.findByDisplayValue("bom dia, turma");
  await userEvent.clear(campo);
  await userEvent.type(campo, "bom dia, pessoal");
  await userEvent.tab();
  await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/salvo/i));
});

test("conflito de versão mostra aviso e não perde o que o professor digitou", async () => {
  mockPadrao({
    "PATCH /api/segmentos/s1": () => jsonResponse({ error_code: "SEGMENTO_DESATUALIZADO",
      message: "Este trecho foi alterado em outra aba. Recarregue a página para ver a versão atual." }, 409),
  });
  renderApp("/aulas/a1/transcricao");
  const campo = await screen.findByDisplayValue("bom dia, turma");
  await userEvent.clear(campo);
  await userEvent.type(campo, "texto novo");
  await userEvent.tab();
  expect(await screen.findByRole("alert")).toHaveTextContent(/alterado em outra aba/i);
  expect(screen.getByDisplayValue("texto novo")).toBeInTheDocument();
});

test("trocar o falante de um segmento", async () => {
  const spy = mockPadrao({
    "PATCH /api/segmentos/s1": () => jsonResponse({ ...SEGMENTO_1, papel: "ALUNO", version: 2 }),
  });
  renderApp("/aulas/a1/transcricao");
  await userEvent.click(await screen.findByRole("button", { name: /marcar como estudante/i }));
  const patch = spy.mock.calls.find(([, i]) => i?.method === "PATCH");
  expect(JSON.parse(String(patch![1]!.body))).toMatchObject({ papel: "ALUNO" });
});

test("cada trecho tem um controle de áudio do seu próprio momento", async () => {
  // spec §8.3: "ouvir é como se conserta atribuição errada" — o professor decide quem
  // falou pelo áudio, não adivinhando pelo texto do ASR (a evidência mais fraca).
  mockPadrao();
  renderApp("/aulas/a1/transcricao");
  const audio = await screen.findByLabelText(/áudio do trecho de 0:00/i);
  expect(audio).toHaveAttribute("src", "/api/aulas/a1/audio?inicio_ms=0&fim_ms=2000");
  // Um bloco de cinco minutos tem dezenas de trechos: sem isto o navegador baixaria
  // (e o servidor recortaria com ffmpeg) todos eles ao abrir a página.
  expect(audio).toHaveAttribute("preload", "none");
});

test("navega entre blocos de cinco minutos", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas/a1/transcricao?bloco=0": () => jsonResponse(bloco([SEGMENTO_1], 0, 10)),
    "GET /api/aulas/a1/transcricao?bloco=1": () =>
      jsonResponse(bloco([{ ...SEGMENTO_1, id: "s2", texto: "outro trecho" }], 1, 10)),
  });
  renderApp("/aulas/a1/transcricao");
  expect(await screen.findByText(/bloco 1 de 10/i)).toBeInTheDocument();
  await userEvent.click(await screen.findByRole("button", { name: /próximos 5 minutos/i }));
  expect(await screen.findByText(/bloco 2 de 10/i)).toBeInTheDocument();
});

test("o botão de bloco anterior começa desabilitado", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas/a1/transcricao?bloco=0": () => jsonResponse(bloco([SEGMENTO_1], 0, 10)),
  });
  renderApp("/aulas/a1/transcricao");
  expect(await screen.findByRole("button", { name: /5 minutos anteriores/i })).toBeDisabled();
});

test("dá para seguir sem revisar nada", async () => {
  const spy = mockPadrao({
    "POST /api/aulas/a1/transcricao/concluir": () => jsonResponse({ id: "a1", status: "READY_FOR_FIAS" }),
  });
  renderApp("/aulas/a1/transcricao");
  await userEvent.click(await screen.findByRole("button", { name: /está bom assim/i }));
  expect(spy.mock.calls.some(([u, i]) => String(u).endsWith("/concluir") && i?.method === "POST")).toBe(true);
  await waitFor(() => expect(window.location.pathname).toBe("/aulas/a1"));
});

test("cada segmento é um grupo rotulado com o horário", async () => {
  mockPadrao();
  renderApp("/aulas/a1/transcricao");
  expect(await screen.findByRole("group", { name: /trecho de 0:00/i })).toBeInTheDocument();
});
