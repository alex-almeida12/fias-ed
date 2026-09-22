import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  // ponytail: alguns testes (ex.: lint.test.ts) rodam com @vitest-environment node,
  // onde `document` não existe; guarda evita ReferenceError nesses arquivos.
  if (typeof document !== "undefined") {
    document.cookie = "fias_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
  }
});
