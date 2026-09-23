import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { jsonResponse, mockApi, PROFESSORA, renderApp } from "../test-utils";

const AULA = { id: "a1", lesson_date: "2026-09-22", turma: { id: "t1", name: "9º B" },
  disciplina: { id: "d1", name: "Ciências" }, note: null, error_code: null, error_message: null, audio: null,
  upload_pendente: null, job_ativo: false, alterada_pelo_admin_em: null, status: "READY_FOR_SPEAKER_REVIEW" };

const VOZES = { vozes: [
  { rotulo: "voz-1", tempo_total_ms: 1_680_000, n_segmentos: 142, amostras: [{ inicio_ms: 0, fim_ms: 4000 }] },
  { rotulo: "voz-2", tempo_total_ms: 420_000, n_segmentos: 58, amostras: [] },
] };

function mockPadrao(extra: Record<string, () => Response> = {}) {
  return mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas/a1": () => jsonResponse(AULA),
    "GET /api/aulas/a1/vozes": () => jsonResponse(VOZES),
    ...extra,
  });
}

test("lista as vozes com tempo e quantidade de momentos", async () => {
  mockPadrao();
  renderApp("/aulas/a1/vozes");
  expect(await screen.findByText("Voz 1")).toBeInTheDocument();
  expect(screen.getByText(/28 min de fala/)).toBeInTheDocument();
  expect(screen.getByText(/142 momentos/)).toBeInTheDocument();
  expect(screen.getByText("Voz 2")).toBeInTheDocument();
  expect(screen.getByText(/7 min de fala/)).toBeInTheDocument();
  expect(screen.getByText(/58 momentos/)).toBeInTheDocument();
});

test("a tela nunca chama as vozes de aluno", async () => {
  // O vocabulário importa: rotular como "Aluno 2" antes de o professor escolher
  // inventa uma identidade que o produto promete não criar (§48). Isso vale para
  // QUALQUER texto da tela, não só para o rótulo da voz — inclusive a frase de
  // instrução, que não pode dizer "ALUNO" antes da escolha existir.
  mockPadrao();
  renderApp("/aulas/a1/vozes");
  await screen.findByText("Voz 1");
  expect(screen.queryByText(/aluno/i)).not.toBeInTheDocument();
});

test("cada trecho de áudio tem nome acessível com a voz e o momento", async () => {
  mockPadrao();
  renderApp("/aulas/a1/vozes");
  await screen.findByText("Voz 1");
  const audios = document.querySelectorAll("audio");
  // voz-1 tem uma amostra, voz-2 não tem nenhuma (amostras: [])
  expect(audios).toHaveLength(1);
  expect(audios[0]).toHaveAttribute("aria-label", "Trecho da voz 1 em 0:00");
  expect(audios[0]).toHaveAttribute("src", "/api/aulas/a1/audio?inicio_ms=0&fim_ms=4000");
});

test("escolher uma voz manda o rótulo e navega para a revisão da transcrição", async () => {
  const spy = mockPadrao({
    "POST /api/aulas/a1/vozes/escolher": () => jsonResponse({ ...AULA, status: "READY_FOR_TRANSCRIPT_REVIEW" }),
  });
  renderApp("/aulas/a1/vozes");
  const botoes = await screen.findAllByRole("button", { name: /esta voz é a minha/i });
  await userEvent.click(botoes[0]);
  const post = spy.mock.calls.find(([, init]) => init?.method === "POST");
  expect(JSON.parse(String(post![1]!.body))).toEqual({ rotulo: "voz-1" });
  await waitFor(() => expect(window.location.pathname).toBe("/aulas/a1"));
});

test("erro ao escolher mostra aviso e não navega para fora da tela", async () => {
  mockPadrao({
    "POST /api/aulas/a1/vozes/escolher": () => jsonResponse({ error_code: "VOZ_INVALIDA", message: "Escolha uma das vozes da lista." }, 422),
  });
  renderApp("/aulas/a1/vozes");
  const botoes = await screen.findAllByRole("button", { name: /esta voz é a minha/i });
  await userEvent.click(botoes[0]);
  expect(await screen.findByRole("alert")).toHaveTextContent("Escolha uma das vozes da lista.");
  expect(window.location.pathname).toBe("/aulas/a1/vozes");
});
