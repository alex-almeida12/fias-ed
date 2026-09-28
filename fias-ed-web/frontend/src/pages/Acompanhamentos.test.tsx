import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { jsonResponse, lerQr, mockApi, PROFESSORA, renderApp } from "../test-utils";

const ACOMPANHAMENTO = {
  id: "c1", turma: { id: "t1", name: "9º B" }, disciplina: { id: "d1", name: "História" },
  n_aulas_previstas: 8, iniciado_em: "2026-03-01", encerrado_em: null, links_qti: [],
};

const LINK_VIVO = { id: "lk1", expira_em: "2026-10-03T00:00:00Z", limite_respostas: 33, coletado_em: "2026-09-26" };

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

// A partir daqui: Task 6 (w3b) — o professor gera e revoga o link do questionário nativo
// pela própria tela, sem passar pelo Postman. O teste seguinte depende de rodar logo depois
// deste (nenhum localStorage.clear() entre os dois, de propósito — veja o comentário nele).
async function gerarLink() {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/ciclos": () => jsonResponse([ACOMPANHAMENTO]),
    "POST /api/ciclos/c1/qti/link": () => jsonResponse(
      { id: "lk1", url: "http://x/responder/tok123", expira_em: "2026-10-03T00:00:00Z", limite_respostas: 33 }, 201),
  });
  renderApp("/ciclos");
  await userEvent.click(await screen.findByRole("button", { name: /gerar link/i }));
  const dialog = screen.getByRole("dialog");
  await userEvent.type(within(dialog).getByLabelText(/quantos estudantes/i), "30");
  await userEvent.click(within(dialog).getByRole("button", { name: /^gerar$/i }));
  await screen.findByText(/responder\/tok123/);
}

test("gerar o link mostra a url uma vez, com aviso de que não se recupera", async () => {
  await gerarLink();
  expect(screen.getByText(/responder\/tok123/)).toBeInTheDocument();
  expect(screen.getByText(/não será possível vê-lo de novo/i)).toBeInTheDocument();
});

test("gerar o link mostra o QR code, que decodifica para a url devolvida", async () => {
  await gerarLink();
  const qr = screen.getByRole("img", { name: /qr code do link/i });
  expect(lerQr(qr as unknown as SVGSVGElement)).toBe("http://x/responder/tok123");
});

test("mostrar para projetar abre o QR grande num diálogo", async () => {
  await gerarLink();
  await userEvent.click(screen.getByRole("button", { name: /mostrar para projetar/i }));
  const dialogo = screen.getByRole("dialog");
  const qr = within(dialogo).getByRole("img", { name: /qr code do link/i });
  expect(lerQr(qr as unknown as SVGSVGElement)).toBe("http://x/responder/tok123");
});

test("a tela não mostra o link antigo ao reabrir a lista", async () => {
  // GET /api/ciclos nunca devolve token; se a tela o exibisse de memória (ou pior, guardada
  // em localStorage), o segredo sobreviveria à sessão sem o servidor saber. Não há
  // localStorage.clear() aqui de propósito: se o teste anterior gerasse um link e o
  // implementasse persistindo-o fora do React, ele vazaria para este teste.
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/ciclos": () => jsonResponse([ACOMPANHAMENTO]),
  });
  renderApp("/ciclos");
  await screen.findByRole("heading", { name: /meus acompanhamentos/i });
  expect(screen.queryByText(/responder\//)).not.toBeInTheDocument();
  expect(screen.queryByRole("img", { name: /qr code/i })).not.toBeInTheDocument();
});

test("o diálogo de gerar manda os três campos no corpo", async () => {
  const spy = mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/ciclos": () => jsonResponse([ACOMPANHAMENTO]),
    "POST /api/ciclos/c1/qti/link": () => jsonResponse(
      { id: "lk1", url: "http://x/responder/tok999", expira_em: "2026-10-03T00:00:00Z", limite_respostas: 33 }, 201),
  });
  renderApp("/ciclos");
  await userEvent.click(await screen.findByRole("button", { name: /gerar link/i }));
  const dialog = screen.getByRole("dialog");
  await userEvent.type(within(dialog).getByLabelText(/quantos estudantes/i), "30");
  await userEvent.clear(within(dialog).getByLabelText(/quando a turma vai responder/i));
  await userEvent.type(within(dialog).getByLabelText(/quando a turma vai responder/i), "2026-09-20");
  await userEvent.clear(within(dialog).getByLabelText(/por quantos dias/i));
  await userEvent.type(within(dialog).getByLabelText(/por quantos dias/i), "14");
  await userEvent.click(within(dialog).getByRole("button", { name: /^gerar$/i }));
  await screen.findByText(/responder\/tok999/);

  const chamada = spy.mock.calls.find(([url, init]) => url === "/api/ciclos/c1/qti/link" && init?.method === "POST");
  const corpo = JSON.parse(String(chamada![1]!.body)) as Record<string, unknown>;
  expect(corpo).toEqual({ n_estudantes: 30, dias: 14, coletado_em: "2026-09-20" });
});

test("o diálogo de gerar avisa que um novo link desativa o anterior da mesma data", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/ciclos": () => jsonResponse([ACOMPANHAMENTO]),
  });
  renderApp("/ciclos");
  await userEvent.click(await screen.findByRole("button", { name: /gerar link/i }));
  expect(within(screen.getByRole("dialog")).getByText(/desativa o anterior/i)).toBeInTheDocument();
});

test("ciclo com link vivo mostra a ação de revogar", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/ciclos": () => jsonResponse([{ ...ACOMPANHAMENTO, links_qti: [LINK_VIVO] }]),
  });
  renderApp("/ciclos");
  expect(await screen.findByRole("button", { name: /revogar link/i })).toBeInTheDocument();
});

test("ciclo sem link vivo não mostra a ação de revogar", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/ciclos": () => jsonResponse([ACOMPANHAMENTO]),
  });
  renderApp("/ciclos");
  await screen.findByText("9º B · História");
  expect(screen.queryByRole("button", { name: /revogar link/i })).not.toBeInTheDocument();
});

test("revogar um link chama POST /api/qti/links/{id}/revogar com o id certo e a lista se atualiza", async () => {
  let revogado = false;
  const spy = mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/ciclos": () => jsonResponse([{ ...ACOMPANHAMENTO, links_qti: revogado ? [] : [LINK_VIVO] }]),
    "POST /api/qti/links/lk1/revogar": () => { revogado = true; return jsonResponse(null, 204); },
  });
  renderApp("/ciclos");
  await userEvent.click(await screen.findByRole("button", { name: /revogar link/i }));
  await userEvent.click(await screen.findByRole("button", { name: /confirmar revogação/i }));
  await waitFor(() => expect(screen.queryByRole("button", { name: /revogar link/i })).not.toBeInTheDocument());
  expect(spy.mock.calls.some(([url, init]) => url === "/api/qti/links/lk1/revogar" && init?.method === "POST")).toBe(true);
});
