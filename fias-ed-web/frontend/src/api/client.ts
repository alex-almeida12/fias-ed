import type { Aula } from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public extra: Record<string, unknown> = {},
  ) {
    super(message);
  }
}

const GENERIC = "Algo deu errado. Tente novamente.";

// Mensagem quando a resposta de erro não é o JSON da API (ex.: página HTML do proxy).
function fallbackMessage(status: number): string {
  if (status === 413) return "O arquivo é grande demais para ser enviado. Tente exportar o áudio em MP3 ou M4A, que ocupam menos espaço.";
  if (status === 502 || status === 503 || status === 504) return "O sistema não está respondendo agora. Aguarde um instante e tente de novo.";
  return GENERIC;
}

function toApiError(status: number, data: Record<string, unknown> | null): ApiError {
  const body = data ?? {};
  const code = typeof body.error_code === "string" ? body.error_code : "UNKNOWN";
  const message = typeof body.message === "string" ? body.message : fallbackMessage(status);
  return new ApiError(status, code, message, body);
}

// Sessão expirada (401 fora das rotas em que 401 é resposta esperada): o AuthProvider registra
// um tratador que limpa a sessão no cliente e leva à tela de entrada.
const OWN_401 = new Set(["/auth/login", "/auth/password", "/auth/logout"]);
let onUnauthenticated: (() => void) | null = null;

export function setUnauthenticatedHandler(handler: (() => void) | null): void {
  onUnauthenticated = handler;
}

function notify401(status: number, path: string): void {
  if (status === 401 && !OWN_401.has(path)) onUnauthenticated?.();
}

function csrfToken(): string {
  const match = document.cookie.match(/(?:^|; )fias_csrf=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : "";
}

export async function api<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, ...rest } = init;
  const method = (rest.method ?? "GET").toUpperCase();
  const headers = new Headers(rest.headers);
  if (method !== "GET") headers.set("X-CSRF-Token", csrfToken());
  let body = rest.body;
  if (json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(json);
  }
  const res = await fetch(`/api${path}`, { ...rest, method, headers, body, credentials: "same-origin" });
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    notify401(res.status, path);
    throw toApiError(res.status, data);
  }
  return data as T;
}

export function uploadAudio(aulaId: string, file: File, onProgress: (fraction: number) => void): Promise<Aula> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", `/api/aulas/${aulaId}/audio`);
    xhr.withCredentials = true;
    xhr.setRequestHeader("X-CSRF-Token", csrfToken());
    xhr.setRequestHeader("X-Filename", encodeURIComponent(file.name));
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(e.loaded / e.total);
    };
    xhr.onload = () => {
      let data: Record<string, unknown> | null = null;
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        /* resposta sem JSON */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data as unknown as Aula);
      else {
        notify401(xhr.status, `/aulas/${aulaId}/audio`);
        reject(toApiError(xhr.status, data));
      }
    };
    xhr.onerror = () => reject(new ApiError(0, "NETWORK", "Não foi possível enviar o arquivo. Verifique a conexão."));
    xhr.send(file);
  });
}

export async function sendAndProcess(aulaId: string, file: File, onProgress: (fraction: number) => void): Promise<Aula> {
  await uploadAudio(aulaId, file, onProgress);
  return api<Aula>(`/aulas/${aulaId}/processar`, { method: "POST" });
}
