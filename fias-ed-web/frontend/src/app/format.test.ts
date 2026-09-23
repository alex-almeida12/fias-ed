import { afterEach, expect, test, vi } from "vitest";
import { formatBytes, formatDate, formatDuration, formatTimestamp, localDateInput } from "./format";

test("formatDate", () => expect(formatDate("2026-09-22")).toBe("22/09/2026"));
test("formatDuration", () => {
  expect(formatDuration(65_000)).toBe("1 min");
  expect(formatDuration(45 * 60_000)).toBe("45 min");
  expect(formatDuration(3_900_000)).toBe("1h05");
});
// Task 8: nome acessível de cada trecho de áudio ("Trecho da voz 1 em 0:04").
test("formatTimestamp", () => {
  expect(formatTimestamp(0)).toBe("0:00");
  expect(formatTimestamp(4_000)).toBe("0:04");
  expect(formatTimestamp(65_000)).toBe("1:05");
  expect(formatTimestamp(600_000)).toBe("10:00");
});
test("formatBytes", () => {
  expect(formatBytes(1_610_612_736)).toBe("1,5 GB");
  expect(formatBytes(2_500_000)).toBe("2,4 MB");
});

afterEach(() => {
  vi.useRealTimers();
});

// `new Date(y, m, d, h, min)` interpreta os componentes como hora LOCAL (não UTC), assim
// como `getFullYear`/`getMonth`/`getDate`. O teste fica independente do fuso da máquina que
// o executa: em qualquer fuso, 22/09/2026 às 23:30 "local" deve formatar como "2026-09-22"
// — o bug corrigido usava `toISOString()` (UTC), que em fusos com offset negativo (ex.:
// Brasil, UTC-3) adiantaria a data à noite.
test("localDateInput usa a data local, não UTC, mesmo à noite", () => {
  const noiteLocal = new Date(2026, 8, 22, 23, 30);
  expect(localDateInput(noiteLocal)).toBe("2026-09-22");
});

test("localDateInput preenche mês e dia com zero à esquerda", () => {
  expect(localDateInput(new Date(2026, 0, 5, 8, 0))).toBe("2026-01-05");
});

test("localDateInput() sem argumento usa o relógio do sistema", () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date(2026, 8, 22, 23, 30));
  expect(localDateInput()).toBe("2026-09-22");
});
