import { vi } from "vitest";
import { render } from "@testing-library/react";
import { App } from "./app/App";

export function jsonResponse(body: unknown, status = 200): Response {
  if (status === 204) return new Response(null, { status });
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

type Handler = (init: RequestInit | undefined, url: string) => Response | Promise<Response>;

export function mockApi(handlers: Record<string, Handler>) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const key = `${(init?.method ?? "GET").toUpperCase()} ${url}`;
    const handler = handlers[key];
    if (!handler) throw new Error(`Rota não simulada: ${key}`);
    return handler(init, url);
  });
}

export function renderApp(path: string) {
  window.history.pushState({}, "", path);
  return render(<App />);
}

export const PROFESSORA = {
  id: "p1", username: "ana", display_name: "Ana Souza", role: "PROFESSOR" as const,
  must_change_password: false, acting_as: null,
};
export const ADMIN = { ...PROFESSORA, id: "a1", username: "admin", display_name: "Pesquisador", role: "ADMIN_LOCAL" as const };
