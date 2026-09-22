export function formatDate(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${y}`;
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

export function formatDuration(ms: number): string {
  const minutes = Math.floor(ms / 60_000);
  const hours = Math.floor(minutes / 60);
  if (hours === 0) return `${minutes} min`;
  return `${hours}h${String(minutes % 60).padStart(2, "0")}`;
}

export function formatBytes(n: number): string {
  const gb = n / 1024 ** 3;
  const value = gb >= 1 ? gb : n / 1024 ** 2;
  const unit = gb >= 1 ? "GB" : "MB";
  return `${value.toFixed(1).replace(/\.0$/, "").replace(".", ",")} ${unit}`;
}

/**
 * Data local (não UTC) no formato `YYYY-MM-DD` esperado por `<input type="date">`.
 * `date.toISOString().slice(0, 10)` usaria a data em UTC: à noite em fusos com offset
 * negativo (ex.: Brasil, UTC-3), isso adiantaria o campo para o dia seguinte.
 */
export function localDateInput(date: Date = new Date()): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}
