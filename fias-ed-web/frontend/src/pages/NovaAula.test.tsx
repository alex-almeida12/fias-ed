import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { ApiError, sendAndProcess } from "../api/client";
import { jsonResponse, mockApi, PROFESSORA, renderApp } from "../test-utils";

vi.mock("../api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/client")>()),
  sendAndProcess: vi.fn(),
}));

const ESCOLA = { id: "e1", name: "Escola A", municipality: "Mossoró", region: "Nordeste" };
const TURMA = { id: "t1", name: "9º B", school_year: 2026, level: null, escola: ESCOLA };
const AULA = { id: "a1", lesson_date: "2026-09-22", status: "DRAFT", turma: { id: "t1", name: "9º B" },
  disciplina: { id: "d1", name: "Ciências" }, note: null, error_code: null, error_message: null, audio: null,
  upload_pendente: null, job_ativo: false, alterada_pelo_admin_em: null };

// Nota: chaves obrigatórias aqui — mockReset() retorna o próprio mock (uma função); uma
// arrow sem chaves devolveria essa função ao runner, que a trataria como callback de
// teardown do hook e a invocaria (sendAndProcess() sem argumentos) após cada teste.
beforeEach(() => {
  vi.mocked(sendAndProcess).mockReset();
});

test("preenche, seleciona o áudio e processa a aula", async () => {
  vi.mocked(sendAndProcess).mockResolvedValue({ ...AULA, status: "AUDIO_IMPORTED", job_ativo: true });
  const spy = mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/turmas": () => jsonResponse([TURMA]),
    "GET /api/disciplinas": () => jsonResponse([{ id: "d1", name: "Ciências" }]),
    "GET /api/escolas": () => jsonResponse([ESCOLA]),
    "POST /api/aulas": () => jsonResponse(AULA, 201),
    "GET /api/aulas/a1": () => jsonResponse({ ...AULA, status: "AUDIO_IMPORTED", job_ativo: true }),
  });
  renderApp("/aulas/nova");
  await screen.findByRole("option", { name: /9º B/ });
  await userEvent.selectOptions(screen.getByLabelText("Turma"), "t1");
  await userEvent.selectOptions(screen.getByLabelText("Disciplina"), "d1");
  expect(screen.getByText("Selecione o arquivo de áudio gravado durante sua aula.")).toBeInTheDocument();
  const file = new File(["x"], "aula.mp3", { type: "audio/mpeg" });
  await userEvent.upload(screen.getByLabelText("Arquivo de áudio"), file);
  expect(screen.getByText(/aula\.mp3/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Processar aula" }));
  await waitFor(() => expect(window.location.pathname).toBe("/aulas/a1"));
  const post = spy.mock.calls.find(([, init]) => init?.method === "POST");
  expect(JSON.parse(String(post![1]!.body))).toMatchObject({ turma_id: "t1", disciplina_id: "d1" });
  expect(vi.mocked(sendAndProcess)).toHaveBeenCalledWith("a1", file, expect.any(Function));
});

test("processar fica desabilitado sem arquivo", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/turmas": () => jsonResponse([TURMA]),
    "GET /api/disciplinas": () => jsonResponse([{ id: "d1", name: "Ciências" }]),
    "GET /api/escolas": () => jsonResponse([ESCOLA]),
  });
  renderApp("/aulas/nova");
  await screen.findByRole("option", { name: /9º B/ });
  await userEvent.selectOptions(screen.getByLabelText("Turma"), "t1");
  expect(screen.getByRole("button", { name: "Processar aula" })).toBeDisabled();
});

test("nova turma com escola duplicada oferece usar a existente", async () => {
  let turmas: unknown[] = [];
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/turmas": () => jsonResponse(turmas),
    "GET /api/disciplinas": () => jsonResponse([]),
    "GET /api/escolas": () => jsonResponse([]),
    "POST /api/escolas": () => jsonResponse({ error_code: "ESCOLA_DUPLICADA",
      message: "Já existe uma escola com este nome neste município.", duplicatas: [ESCOLA] }, 409),
    "POST /api/turmas": (init) => {
      expect(JSON.parse(String(init!.body)).escola_id).toBe("e1");
      turmas = [TURMA];
      return jsonResponse(TURMA, 201);
    },
  });
  renderApp("/aulas/nova");
  await userEvent.selectOptions(await screen.findByLabelText("Turma"), "__nova__");
  await userEvent.type(screen.getByLabelText("Nome da turma"), "9º B");
  await userEvent.selectOptions(screen.getByLabelText("Escola"), "__nova__");
  await userEvent.type(screen.getByLabelText("Nome da escola"), "escola a");
  await userEvent.type(screen.getByLabelText("Município"), "Mossoró");
  await userEvent.click(screen.getByRole("button", { name: "Salvar turma" }));
  expect(await screen.findByText("Já existe uma escola com este nome neste município.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Usar Escola A (Mossoró)" }));
  await waitFor(() => expect(screen.getByLabelText("Turma")).toHaveValue("t1"));
});

// Ruling P9: quando a aula já foi criada mas o upload/processar falha, a mensagem de erro
// deve ser levada para a página da Aula via navigation state, não perdida.
test("upload falha após criar a aula: mensagem aparece na página da aula", async () => {
  vi.mocked(sendAndProcess).mockRejectedValue(new ApiError(413, "AUDIO_TOO_LARGE", "O arquivo é maior que o limite permitido."));
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/turmas": () => jsonResponse([TURMA]),
    "GET /api/disciplinas": () => jsonResponse([{ id: "d1", name: "Ciências" }]),
    "GET /api/escolas": () => jsonResponse([ESCOLA]),
    "POST /api/aulas": () => jsonResponse(AULA, 201),
    "GET /api/aulas/a1": () => jsonResponse(AULA),
  });
  renderApp("/aulas/nova");
  await screen.findByRole("option", { name: /9º B/ });
  await userEvent.selectOptions(screen.getByLabelText("Turma"), "t1");
  await userEvent.selectOptions(screen.getByLabelText("Disciplina"), "d1");
  const file = new File(["x"], "aula.mp3", { type: "audio/mpeg" });
  await userEvent.upload(screen.getByLabelText("Arquivo de áudio"), file);
  await userEvent.click(screen.getByRole("button", { name: "Processar aula" }));
  await waitFor(() => expect(window.location.pathname).toBe("/aulas/a1"));
  expect(await screen.findByRole("alert")).toHaveTextContent("O arquivo é maior que o limite permitido.");
});

// Ruling P15: erro ao carregar turmas/disciplinas/escolas não deve ficar silencioso.
test("erro ao carregar turmas mostra aviso", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/turmas": () => jsonResponse({ error_code: "ERRO", message: "Falha ao listar turmas." }, 500),
    "GET /api/disciplinas": () => jsonResponse([]),
    "GET /api/escolas": () => jsonResponse([]),
  });
  renderApp("/aulas/nova");
  expect(await screen.findByRole("alert")).toHaveTextContent("Falha ao listar turmas.");
});
