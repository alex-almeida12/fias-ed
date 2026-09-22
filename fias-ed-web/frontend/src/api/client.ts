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
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, data.error_code ?? "UNKNOWN", data.message ?? GENERIC, data);
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
      let data: Record<string, unknown> = {};
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        /* resposta sem JSON */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data as unknown as Aula);
      else reject(new ApiError(xhr.status, String(data.error_code ?? "UNKNOWN"), String(data.message ?? GENERIC), data));
    };
    xhr.onerror = () => reject(new ApiError(0, "NETWORK", "Não foi possível enviar o arquivo. Verifique a conexão."));
    xhr.send(file);
  });
}

export async function sendAndProcess(aulaId: string, file: File, onProgress: (fraction: number) => void): Promise<Aula> {
  await uploadAudio(aulaId, file, onProgress);
  return api<Aula>(`/aulas/${aulaId}/processar`, { method: "POST" });
}
