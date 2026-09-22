import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { jsonResponse, mockApi, PROFESSORA, renderApp } from "../test-utils";

const BASE = { id: "a1", lesson_date: "2026-09-22", turma: { id: "t1", name: "9º B" },
  disciplina: { id: "d1", name: "Ciências" }, note: null, error_code: null, error_message: null, audio: null,
  upload_pendente: null, job_ativo: false, alterada_pelo_admin_em: null, status: "DRAFT" };

afterEach(() => vi.useRealTimers());

test("erro mostra a mensagem humana e permite enviar outro áudio", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas/a1": () => jsonResponse({ ...BASE, status: "ERROR", error_code: "AUDIO_TOO_SHORT",
      error_message: "O áudio tem menos de 1 minuto. Verifique se é o arquivo certo." }),
  });
  renderApp("/aulas/a1");
  expect(await screen.findByRole("alert")).toHaveTextContent("O áudio tem menos de 1 minuto.");
  expect(screen.getByRole("button", { name: "Selecionar áudio" })).toBeInTheDocument();
});

test("aviso de alteração pelo administrador", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas/a1": () => jsonResponse({ ...BASE, alterada_pelo_admin_em: "2026-09-22T12:00:00+00:00" }),
  });
  renderApp("/aulas/a1");
  expect(await screen.findByText(/Alterada pelo administrador em/)).toBeInTheDocument();
});

test("acompanha o processamento até o áudio ser conferido", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  let calls = 0;
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas/a1": () => {
      calls += 1;
      return jsonResponse(calls === 1
        ? { ...BASE, status: "AUDIO_IMPORTED", job_ativo: true, upload_pendente: { original_filename: "a.wav", size_bytes: 10 } }
        : { ...BASE, status: "AUDIO_VALIDATED", audio: { original_filename: "a.wav", mime_type: "audio/wav",
            size_bytes: 2_000_000, duration_ms: 3_000_000, channels: 1, sample_rate: 16000 } });
    },
  });
  renderApp("/aulas/a1");
  expect(await screen.findByText("Preparando sua aula...")).toBeInTheDocument();
  await act(async () => { await vi.advanceTimersByTimeAsync(3100); });
  await waitFor(() => expect(screen.getByText("Áudio conferido")).toBeInTheDocument());
  expect(screen.getByText("50 min")).toBeInTheDocument();
  expect(document.querySelector("audio")).toHaveAttribute("src", "/api/aulas/a1/audio");
});

test("substituir o áudio pede confirmação", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas/a1": () => jsonResponse({ ...BASE, status: "AUDIO_VALIDATED", audio: { original_filename: "a.wav",
      mime_type: "audio/wav", size_bytes: 10, duration_ms: 70_000, channels: 1, sample_rate: 16000 } }),
  });
  renderApp("/aulas/a1");
  await userEvent.click(await screen.findByRole("button", { name: "Substituir áudio" }));
  expect(screen.getByRole("dialog", { name: "Substituir o áudio?" })).toHaveTextContent("O arquivo anterior será apagado.");
});

test("excluir a aula volta para a lista", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas/a1": () => jsonResponse(BASE),
    "DELETE /api/aulas/a1": () => jsonResponse(null, 204),
    "GET /api/aulas": () => jsonResponse([]),
  });
  renderApp("/aulas/a1");
  await userEvent.click(await screen.findByRole("button", { name: "Excluir aula" }));
  await userEvent.click(screen.getByRole("button", { name: "Excluir definitivamente" }));
  await waitFor(() => expect(window.location.pathname).toBe("/aulas"));
});

// Ruling P15: erro ao excluir não deve ficar silencioso.
test("erro ao excluir mostra aviso e permanece na página da aula", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas/a1": () => jsonResponse(BASE),
    "DELETE /api/aulas/a1": () => jsonResponse({ error_code: "ERRO", message: "Não foi possível excluir." }, 500),
  });
  renderApp("/aulas/a1");
  await userEvent.click(await screen.findByRole("button", { name: "Excluir aula" }));
  await userEvent.click(screen.getByRole("button", { name: "Excluir definitivamente" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível excluir.");
  expect(window.location.pathname).toBe("/aulas/a1");
});
