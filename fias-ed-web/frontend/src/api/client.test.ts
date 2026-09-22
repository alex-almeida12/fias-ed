import { expect, test } from "vitest";
import { api, ApiError } from "./client";
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
