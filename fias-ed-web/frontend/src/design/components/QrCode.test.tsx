import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { render } from "@testing-library/react";
import { expect, test } from "vitest";
import { lerQr } from "../../test-utils";
import { QrCode } from "./QrCode";

const URL_DO_LINK = "http://192.168.137.1:8081/responder/AbC-123_xyzTokenDeTeste0987654321abcdEFGH";

test("o QR desenhado decodifica exatamente para a URL do link", () => {
  const { container } = render(<QrCode valor={URL_DO_LINK} rotulo="QR code do link" />);
  expect(lerQr(container.querySelector("svg")!)).toBe(URL_DO_LINK);
});

test("o QR tem nome acessível", () => {
  const { getByRole } = render(<QrCode valor={URL_DO_LINK} rotulo="QR code do link" />);
  expect(getByRole("img", { name: "QR code do link" })).toBeInTheDocument();
});

// Contraste dos módulos do QR contra o fundo. `contraste-telas.test.ts` enumera pares de
// COR (`color`) sobre FUNDO (`background`) — o QR pinta com `fill`, então segue aqui o
// mesmo raciocínio de FaixaDeTempo.test.ts: ler o CSS de verdade em vez de repetir as
// cores no teste, para que uma mudança na declaração mude o resultado do teste.
const ler = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), "utf8");
const TOKENS = ler("../../../../../fias-ed-shared/design-tokens/build/tokens.css");
const COMPONENTES = ler("../components.css");

const VARIAVEIS = new Map(
  [...TOKENS.matchAll(/--([\w-]+)\s*:\s*([^;}]+)[;}]/g)].map(([, nome, valor]) => [nome, valor.trim()]),
);

function hex(valor: string): string {
  let v = valor.trim();
  for (let i = 0; i < 10 && v.startsWith("var("); i += 1) {
    v = (VARIAVEIS.get(v.slice(4, -1).trim().replace(/^--/, "")) ?? "").trim();
  }
  expect(v, `valor de cor não resolvido a partir de "${valor}"`).toMatch(/^#[0-9a-fA-F]{6}$/);
  return v;
}

function declaracao(seletor: string, propriedade: string): string {
  const abre = COMPONENTES.indexOf(`${seletor} {`);
  expect(abre, `regra ${seletor} não existe em components.css`).toBeGreaterThan(-1);
  const corpo = COMPONENTES.slice(abre + seletor.length + 2, COMPONENTES.indexOf("}", abre));
  const par = corpo.split(";").find((d) => d.trim().startsWith(`${propriedade}:`));
  expect(par, `${seletor} não declara ${propriedade}`).toBeDefined();
  return par!.slice(par!.indexOf(":") + 1).trim();
}

function luminancia(cor: string): number {
  const canais = [1, 3, 5].map((i) => parseInt(cor.slice(i, i + 2), 16) / 255);
  const [r, g, b] = canais.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
function contraste(a: string, b: string): number {
  const [claro, escuro] = [luminancia(a), luminancia(b)].sort((x, y) => y - x);
  return (claro + 0.05) / (escuro + 0.05);
}

test("os módulos do QR usam tokens de cor, com contraste de sobra contra o fundo", () => {
  const modulos = hex(declaracao(".qr__modulos", "fill"));
  const fundo = hex(declaracao(".qr__fundo", "fill"));
  expect(declaracao(".qr__modulos", "fill")).toBe("var(--color-navy)");
  expect(declaracao(".qr__fundo", "fill")).toBe("var(--color-white)");
  // Um leitor de QR não é texto: o piso relevante é o 3:1 do WCAG 1.4.11 para
  // elemento gráfico, mas navy sobre branco já mede 10,44:1 (o mesmo par que
  // contraste-telas.test.ts confere).
  expect(contraste(modulos, fundo)).toBeGreaterThanOrEqual(3);
});
