import { afterEach, expect, test, vi } from "vitest";
import { api, ApiError, setUnauthenticatedHandler, uploadAudio } from "./client";
import { jsonResponse, mockApi } from "../test-utils";

test("GET não envia CSRF; POST envia o valor do cookie", async () => {
  document.cookie = "fias_csrf=abc123";
  const spy = mockApi({
    "GET /api/auth/me": () => jsonResponse({ ok: 1 }),
    "POST /api/aulas": () => jsonResponse({ id: "1" }, 201),
  });
  await api("/auth/me");
  await api("/aulas", { method: "POST", json: { a: 1 } });
  const [, getInit] = spy.mock.calls[0];
  const [, postInit] = spy.mock.calls[1];
  expect(new Headers(getInit!.headers).get("X-CSRF-Token")).toBeNull();
  expect(new Headers(postInit!.headers).get("X-CSRF-Token")).toBe("abc123");
  expect(postInit!.body).toBe(JSON.stringify({ a: 1 }));
  expect(postInit!.credentials).toBe("same-origin");
});

test("erro vira ApiError com código e mensagem da API", async () => {
  mockApi({ "GET /api/aulas/x": () => jsonResponse({ error_code: "AULA_NAO_ENCONTRADA", message: "Aula não encontrada." }, 404) });
  await expect(api("/aulas/x")).rejects.toMatchObject({ status: 404, code: "AULA_NAO_ENCONTRADA", message: "Aula não encontrada." });
  await expect(api("/aulas/x")).rejects.toBeInstanceOf(ApiError);
});

test("204 devolve undefined", async () => {
  mockApi({ "DELETE /api/aulas/1": () => jsonResponse(null, 204) });
  expect(await api("/aulas/1", { method: "DELETE" })).toBeUndefined();
});

function htmlResponse(status: number): Response {
  return new Response("<html><body><h1>Erro</h1><hr><center>nginx</center></body></html>", {
    status, headers: { "Content-Type": "text/html" },
  });
}

test.each([
  [413, "O arquivo é grande demais para ser enviado. Tente exportar o áudio em MP3 ou M4A, que ocupam menos espaço."],
  [502, "O sistema não está respondendo agora. Aguarde um instante e tente de novo."],
  [503, "O sistema não está respondendo agora. Aguarde um instante e tente de novo."],
  [504, "O sistema não está respondendo agora. Aguarde um instante e tente de novo."],
  [500, "Algo deu errado. Tente novamente."],
])("erro %i sem JSON (página do proxy) vira mensagem em português", async (status, message) => {
  mockApi({ "POST /api/aulas": () => htmlResponse(status) });
  await expect(api("/aulas", { method: "POST", json: {} })).rejects.toMatchObject({ status, code: "UNKNOWN", message });
});

// XHR falso: só o necessário para uploadAudio.
class FakeXhr {
  static next: { status: number; responseText: string };
  status = 0;
  responseText = "";
  withCredentials = false;
  upload = { onprogress: null as unknown };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  open() {}
  setRequestHeader() {}
  send() {
    this.status = FakeXhr.next.status;
    this.responseText = FakeXhr.next.responseText;
    queueMicrotask(() => this.onload?.());
  }
}

afterEach(() => {
  vi.unstubAllGlobals();
  setUnauthenticatedHandler(null);
});

test("upload com 413 em HTML (proxy) mostra mensagem de arquivo grande", async () => {
  vi.stubGlobal("XMLHttpRequest", FakeXhr);
  FakeXhr.next = { status: 413, responseText: "<html>413 Request Entity Too Large</html>" };
  await expect(uploadAudio("a1", new File(["x"], "a.wav"), () => {})).rejects.toMatchObject({
    status: 413, code: "UNKNOWN", message: expect.stringContaining("grande demais"),
  });
});

test("upload com 413 em JSON (nginx) mostra a mensagem da API", async () => {
  vi.stubGlobal("XMLHttpRequest", FakeXhr);
  FakeXhr.next = { status: 413, responseText: JSON.stringify({ error_code: "AUDIO_TOO_LARGE", message: "O arquivo passa de 1,5 GB." }) };
  await expect(uploadAudio("a1", new File(["x"], "a.wav"), () => {})).rejects.toMatchObject({
    status: 413, code: "AUDIO_TOO_LARGE", message: "O arquivo passa de 1,5 GB.",
  });
});

test("upload com 502 sem JSON mostra que o sistema não responde", async () => {
  vi.stubGlobal("XMLHttpRequest", FakeXhr);
  FakeXhr.next = { status: 502, responseText: "<html>502 Bad Gateway</html>" };
  await expect(uploadAudio("a1", new File(["x"], "a.wav"), () => {})).rejects.toMatchObject({
    status: 502, message: "O sistema não está respondendo agora. Aguarde um instante e tente de novo.",
  });
});

test("401 avisa o tratador de sessão expirada, exceto nas rotas de login/senha/saída", async () => {
  const handler = vi.fn();
  setUnauthenticatedHandler(handler);
  const unauth = () => jsonResponse({ error_code: "UNAUTHENTICATED", message: "Entre com seu usuário e senha." }, 401);
  mockApi({
    "GET /api/aulas": unauth,
    "POST /api/auth/login": () => jsonResponse({ error_code: "LOGIN_FAILED", message: "Usuário ou senha incorretos." }, 401),
    "POST /api/auth/password": () => jsonResponse({ error_code: "PASSWORD_WRONG", message: "A senha atual não confere." }, 401),
    "POST /api/auth/logout": unauth,
  });
  await expect(api("/auth/login", { method: "POST", json: {} })).rejects.toMatchObject({ status: 401 });
  await expect(api("/auth/password", { method: "POST", json: {} })).rejects.toMatchObject({ status: 401 });
  await expect(api("/auth/logout", { method: "POST" })).rejects.toMatchObject({ status: 401 });
  expect(handler).not.toHaveBeenCalled();
  await expect(api("/aulas")).rejects.toMatchObject({ status: 401, code: "UNAUTHENTICATED" });
  expect(handler).toHaveBeenCalledTimes(1);
});

test("upload com 401 também avisa o tratador de sessão expirada", async () => {
  const handler = vi.fn();
  setUnauthenticatedHandler(handler);
  vi.stubGlobal("XMLHttpRequest", FakeXhr);
  FakeXhr.next = { status: 401, responseText: JSON.stringify({ error_code: "UNAUTHENTICATED", message: "Entre com seu usuário e senha." }) };
  await expect(uploadAudio("a1", new File(["x"], "a.wav"), () => {})).rejects.toMatchObject({ status: 401 });
  expect(handler).toHaveBeenCalledTimes(1);
});
