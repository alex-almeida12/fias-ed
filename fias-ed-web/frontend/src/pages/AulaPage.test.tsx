import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { jsonResponse, mockApi, PROFESSORA, renderApp } from "../test-utils";

const BASE = { id: "a1", lesson_date: "2026-09-22", turma: { id: "t1", name: "9º B" },
  disciplina: { id: "d1", name: "Ciências" }, note: null, error_code: null, error_message: null, audio: null,
  upload_pendente: null, job_ativo: false, alterada_pelo_admin_em: null, status: "DRAFT",
  acompanhamento: null };

const ACOMPANHAMENTO = { id: "c1", turma: { id: "t1", name: "9º B" }, disciplina: { id: "d1", name: "Ciências" },
  n_aulas_previstas: 8, posicao: "primeira" };

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

// Task 8: o sistema não decide sozinho qual voz é a do professor — READY_FOR_SPEAKER_REVIEW
// leva direto à tela de escolha, em vez de mostrar a Aula parada nesse estado.
test("aula aguardando escolha de voz leva direto à tela de vozes", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas/a1": () => jsonResponse({ ...BASE, status: "READY_FOR_SPEAKER_REVIEW" }),
    "GET /api/aulas/a1/vozes": () => jsonResponse({ vozes: [] }),
  });
  renderApp("/aulas/a1");
  await waitFor(() => expect(window.location.pathname).toBe("/aulas/a1/vozes"));
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
  expect(await screen.findByText("Preparando sua aula…")).toBeInTheDocument();
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

// Task 15: a mensagem de progresso é a do §36 correspondente ao estágio em curso. O
// professor lê o que está acontecendo com a aula dele; a tecnologia fica nos bastidores (§86).
test("aula em transcrição mostra a mensagem do §36, sem jargão", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas/a1": () => jsonResponse({ ...BASE, status: "TRANSCRIBING", job_ativo: true }),
  });
  renderApp("/aulas/a1");
  const aviso = await screen.findByText("Transformando áudio em texto…");
  // role="status" é a única forma de quem usa leitor de tela saber que a página mudou sozinha.
  expect(aviso).toHaveAttribute("role", "status");
  expect(document.body.textContent).not.toMatch(/whisper|pyannote|bertimbau|diariz|infer[êe]ncia|\bmodelo\b|\bASR\b|pipeline/i);
});

test("aula com a voz já escolhida leva para a revisão da transcrição", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas/a1": () => jsonResponse({ ...BASE, status: "READY_FOR_TRANSCRIPT_REVIEW" }),
    "GET /api/aulas/a1/transcricao?bloco=0": () => jsonResponse({ bloco: 0, blocos: 1, segmentos: [] }),
  });
  renderApp("/aulas/a1");
  await userEvent.click(await screen.findByRole("link", { name: "Revisar a transcrição" }));
  await waitFor(() => expect(window.location.pathname).toBe("/aulas/a1/transcricao"));
});

test("aula classificada leva para os padrões de interação, sem vocabulário de julgamento", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas/a1": () => jsonResponse({ ...BASE, status: "FIAS_COMPLETED" }),
    "GET /api/aulas/a1/padroes": () => jsonResponse({ faixa: [], observacoes: [], matriz: [], indices: [] }),
  });
  renderApp("/aulas/a1");
  const link = await screen.findByRole("link", { name: "Ver padrões de interação" });
  // A asserção de ausência só vale depois da de presença: prova que a página carregou.
  expect(document.body.textContent).not.toMatch(/avalia|nota do professor|desempenho|ranking/i);
  await userEvent.click(link);
  await waitFor(() => expect(window.location.pathname).toBe("/aulas/a1/padroes"));
});

// spec §9: áudio sem fala não pode virar beco sem saída — a mensagem humana vem com a
// ação seguinte. E o alerta não está montado junto com a página: entra quando a aula
// chega, que é quando o leitor de tela deve anunciá-lo.
test("áudio sem fala mostra a mensagem humana, a saída, e só anuncia quando a aula chega", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas/a1": () => jsonResponse({ ...BASE, status: "ERROR", error_code: "AUDIO_SEM_FALA",
      error_message: "Não conseguimos identificar fala neste áudio. Confira se o arquivo é mesmo o da aula.",
      audio: { original_filename: "a.wav", mime_type: "audio/wav", size_bytes: 10, duration_ms: 70_000,
        channels: 1, sample_rate: 16000 } }),
  });
  renderApp("/aulas/a1");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(await screen.findByRole("alert")).toHaveTextContent(/não conseguimos identificar fala/i);
  expect(screen.getByRole("button", { name: "Selecionar áudio" })).toBeInTheDocument();
});

// Task 17: o professor descobre o questionário — WAITING_QTI deixa de ser beco sem
// saída: o aviso diz o que falta e leva direto à ação, sem soar como erro dele.
test("aula esperando o questionário mostra o aviso e o link para enviar o relatório", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas/a1": () => jsonResponse({ ...BASE, status: "WAITING_QTI", acompanhamento: ACOMPANHAMENTO }),
  });
  renderApp("/aulas/a1");
  expect(await screen.findByText(/primeira aula do acompanhamento de 9º B/)).toBeInTheDocument();
  const link = screen.getByRole("link", { name: "Enviar o relatório do questionário" });
  expect(link).toHaveAttribute("href", "/ciclos/c1/qti");
});

test("o aviso do questionário não é role=alert — não é erro do professor", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas/a1": () => jsonResponse({ ...BASE, status: "WAITING_QTI", acompanhamento: ACOMPANHAMENTO }),
  });
  renderApp("/aulas/a1");
  await screen.findByRole("link", { name: "Enviar o relatório do questionário" });
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

test("aula fora de qualquer acompanhamento diz isso, sem link quebrado", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas/a1": () => jsonResponse({ ...BASE, acompanhamento: null }),
  });
  renderApp("/aulas/a1");
  expect(await screen.findByText("Fora de qualquer acompanhamento")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Ver o acompanhamento" })).not.toBeInTheDocument();
});

test("aula dentro de um acompanhamento mostra o link para o relatório dele, em qualquer estado", async () => {
  mockApi({
    "GET /api/auth/me": () => jsonResponse(PROFESSORA),
    "GET /api/aulas/a1": () => jsonResponse({ ...BASE, status: "FIAS_COMPLETED", acompanhamento: ACOMPANHAMENTO }),
    "GET /api/aulas/a1/padroes": () => jsonResponse({ faixa: [], observacoes: [], matriz: [], indices: [] }),
  });
  renderApp("/aulas/a1");
  const link = await screen.findByRole("link", { name: "Ver o acompanhamento" });
  expect(link).toHaveAttribute("href", "/ciclos/c1/relatorio");
});
