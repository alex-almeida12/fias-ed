import { expect, test } from "vitest";
import { formatBytes, formatDate, formatDuration } from "./format";

test("formatDate", () => expect(formatDate("2026-09-22")).toBe("22/09/2026"));
test("formatDuration", () => {
  expect(formatDuration(65_000)).toBe("1 min");
  expect(formatDuration(45 * 60_000)).toBe("45 min");
  expect(formatDuration(3_900_000)).toBe("1h05");
});
test("formatBytes", () => {
  expect(formatBytes(1_610_612_736)).toBe("1,5 GB");
  expect(formatBytes(2_500_000)).toBe("2,4 MB");
});
