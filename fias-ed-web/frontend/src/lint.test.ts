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
});
