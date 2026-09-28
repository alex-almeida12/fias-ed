import jsQR from "jsqr";
import { vi } from "vitest";
import { render } from "@testing-library/react";
import { App } from "./app/App";

/** Rasteriza o SVG do <QrCode> (módulos escuros sobre fundo claro) e o decodifica com
 * um leitor independente. É o que prova que o desenho é um QR de verdade e que ele
 * carrega exatamente o texto pedido — e não só que o componente recebeu o texto. */
export function lerQr(svg: SVGSVGElement): string | null {
  const lado = Number(svg.getAttribute("viewBox")!.split(" ")[2]);
  const escala = 8;
  const px = lado * escala;
  const rgba = new Uint8ClampedArray(px * px * 4).fill(255);
  svg.querySelectorAll(".qr__modulos rect").forEach((r) => {
    const x = Number(r.getAttribute("x"));
    const y = Number(r.getAttribute("y"));
    for (let dy = 0; dy < escala; dy++) {
      for (let dx = 0; dx < escala; dx++) {
        const i = ((y * escala + dy) * px + (x * escala + dx)) * 4;
        rgba[i] = rgba[i + 1] = rgba[i + 2] = 0;
      }
    }
  });
  return jsQR(rgba, px, px)?.data ?? null;
}

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
