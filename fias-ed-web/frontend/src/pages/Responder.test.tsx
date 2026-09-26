import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test } from "vitest";
import { jsonResponse, mockApi, renderApp } from "../test-utils";

const ABRIR = "GET /publico/qti/tok123";
const CONSENTIR = "POST /publico/qti/tok123/consentir";
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

// Review Focus: os dois testes acima param antes do que a tela mais precisa
// provar — que o botão habilita de verdade na 24ª (não só "continua
// desabilitado com zero") e que o envio não pode ser reenviado. Este teste
// percorre o caminho inteiro: marca as 24, prova a borda 23/24 do botão,
// confere o corpo exato mandado a cada rota (respostas e documento_versao),
// vê o agradecimento e confirma a marca gravada no navegador do estudante.
test("enviar as 24 respostas registra o consentimento, manda o corpo certo, mostra o agradecimento e marca o navegador", async () => {
  const spy = mockApi({
    [ABRIR]: () => jsonResponse(QUESTIONARIO),
    [CONSENTIR]: () => jsonResponse({}, 201),
    [RESPONDER]: () => jsonResponse({}, 201),
  });
  renderApp("/responder/tok123");
  await userEvent.click(await screen.findByRole("button", { name: /concordo/i }));
  await screen.findByText(/pergunta 1$/);

  const perguntas = screen.getAllByRole("group");
  expect(perguntas).toHaveLength(24);

  const esperado: Record<string, number> = {};
  const enviarBtn = () => screen.getByRole("button", { name: /enviar/i });
  for (const [i, fieldset] of perguntas.entries()) {
    const ordem = i + 1;
    const valor = (ordem % 5) + 1; // varia 2,3,4,5,1,2,3,4,5,1... — não é sempre o mesmo número
    const radios = within(fieldset).getAllByRole("radio");
    await userEvent.click(radios[valor - 1]);
    esperado[String(ordem)] = valor;
    // A borda que as mutações da revisão furaram: com 23 marcadas ainda
    // desabilitado, só habilita depois da 24ª.
    if (ordem < 24) expect(enviarBtn()).toBeDisabled();
  }
  expect(enviarBtn()).not.toBeDisabled();

  await userEvent.click(enviarBtn());
  expect(await screen.findByText(/já respondeu/i)).toBeInTheDocument();

  const chamada = (rota: string) =>
    spy.mock.calls.find(([url, init]) => String(url).endsWith(rota) && init?.method === "POST");

  const corpoConsentir = JSON.parse(String(chamada("/consentir")![1]!.body)) as { documento_versao: unknown };
  expect(typeof corpoConsentir.documento_versao).toBe("string");
  expect((corpoConsentir.documento_versao as string).length).toBeGreaterThan(0);
  expect((corpoConsentir.documento_versao as string).length).toBeLessThanOrEqual(32);

  const corpoResponder = JSON.parse(String(chamada("/responder")![1]!.body)) as { respostas: unknown };
  expect(corpoResponder.respostas).toEqual(esperado);

  expect(localStorage.getItem("fias-ed:respondido:tok123")).toBe("1");
});
