// @vitest-environment node
import { ESLint } from "eslint";
import { expect, test } from "vitest";

test("lint proíbe dangerouslySetInnerHTML e style inline", async () => {
  const eslint = new ESLint();
  const [result] = await eslint.lintText(
    'export const A = () => <div dangerouslySetInnerHTML={{ __html: "x" }} style={{ color: "red" }} />;\n',
    { filePath: "src/exemplo.tsx" },
  );
  const messages = result.messages.map((m) => m.message).join("\n");
  expect(messages).toContain("§59");
  expect(messages).toContain("CSP");
  // Carregar a config do ESLint (flat config + typescript-eslint) custa ~65 s na
  // primeira execução depois de `npm ci`, quando nada está em cache de disco, e
  // ~1 s depois. O timeout padrão do vitest (5 s) reprovava este teste em 100%
  // das execuções frias — que é exatamente o que `npm ci && npm test` faz.
}, 120_000);
