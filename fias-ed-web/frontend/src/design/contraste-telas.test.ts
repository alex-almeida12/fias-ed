// @vitest-environment node
//
// Task 15 (revisão visual): a Regra dos Três Pares Proibidos e o piso de 4,5:1
// (texto normal) / 3:1 (texto grande, ≥24px) do DESIGN.md §Colors, aplicados aos
// pares texto-sobre-fundo que as cinco telas desta fatia realmente produzem —
// NovoCiclo, ImportarQTI, RelatorioAula, RelatorioCiclo e Acompanhamentos.
//
// Mesmo raciocínio de FaixaDeTempo.test.ts: o teste lê o CSS de verdade (não
// repete os tokens aqui), para que uma mudança na declaração de cor mude o
// resultado do teste. A parte que o CSS não decide sozinho — QUEM está dentro
// de QUEM no DOM — vem de ler as cinco páginas (ver comentário de cada par
// abaixo) e é o único pedaço que uma mudança de marcação futura não atualiza
// sozinho; é por isso que a Task 15 pede também a verificação em navegador.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { expect, test } from "vitest";

const ler = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), "utf8");
const TOKENS = ler("../../../../fias-ed-shared/design-tokens/build/tokens.css");
const TOKENS_JSON = JSON.parse(ler("../../../../fias-ed-shared/design-tokens/tokens.json")) as {
  color: { brand: Record<string, string> };
  forbidden_text_pairs: [string, string][];
};
const BASE = ler("./base.css");
const COMPONENTES = ler("./components.css");
const CSS = `${BASE}\n${COMPONENTES}`;

const VARIAVEIS = new Map(
  [...TOKENS.matchAll(/--([\w-]+)\s*:\s*([^;}]+)[;}]/g)].map(([, nome, valor]) => [nome, valor.trim()]),
);

/** Resolve `var(--x)` até chegar no `#RRGGBB` que tokens.css guarda. */
function hex(valor: string): string {
  let v = valor.trim();
  for (let i = 0; i < 10 && v.startsWith("var("); i += 1) {
    v = (VARIAVEIS.get(v.slice(4, -1).trim().replace(/^--/, "")) ?? "").trim();
  }
  expect(v, `valor de cor não resolvido a partir de "${valor}"`).toMatch(/^#[0-9a-fA-F]{6}$/);
  return v;
}

/** As declarações de uma regra do CSS (base.css + components.css), pelo seletor exato. */
function regra(seletor: string): Map<string, string> {
  const abre = CSS.indexOf(`${seletor} {`);
  expect(abre, `regra ${seletor} não existe em base.css/components.css`).toBeGreaterThan(-1);
  const corpo = CSS.slice(abre + seletor.length + 2, CSS.indexOf("}", abre));
  return new Map(
    corpo
      .split(";")
      .filter((d) => d.includes(":"))
      .map((d) => [d.slice(0, d.indexOf(":")).trim(), d.slice(d.indexOf(":") + 1).trim()]),
  );
}

// Contraste do WCAG 2.1 (relação entre luminâncias relativas).
function luminancia(cor: string): number {
  const canais = [1, 3, 5].map((i) => parseInt(cor.slice(i, i + 2), 16) / 255);
  const [r, g, b] = canais.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
function contraste(a: string, b: string): number {
  const [claro, escuro] = [luminancia(a), luminancia(b)].sort((x, y) => y - x);
  return (claro + 0.05) / (escuro + 0.05);
}

test("a régua de contraste bate com a do WCAG em pares conhecidos", () => {
  // Sem isto, um erro na fórmula faria todos os testes abaixo passarem por engano
  // (o mesmo raciocínio do medidor que devolvia "zero achados" para tudo).
  expect(contraste("#FFFFFF", "#000000")).toBeCloseTo(21, 2);
  expect(contraste("#2F4156", "#FFFFFF")).toBeCloseTo(10.44, 1); // navy x branco
  expect(contraste("#567C8D", "#F5EFEB")).toBeCloseTo(3.95, 1); // teal x bege: o par que exige o desvio para navy
});

// O texto efetivo/fundo efetivo de um elemento: a cor que a PRÓPRIA regra declara,
// ou — se ela não declarar nada — a da página (body), porque nada entre o body e
// estes elementos muda a cor. `null` significa "usa o default do body".
function corEfetiva(seletor: string | null): string {
  if (seletor === null) return hex(declaracao("body", "color"));
  const r = regra(seletor);
  return r.has("color") ? hex(r.get("color")!) : hex(declaracao("body", "color"));
}
function fundoEfetivo(seletor: string | null): string {
  if (seletor === null) return hex(declaracao("body", "background"));
  const r = regra(seletor);
  return r.has("background") ? hex(r.get("background")!) : hex(declaracao("body", "background"));
}
function declaracao(seletor: string, propriedade: string): string {
  const valor = regra(seletor).get(propriedade);
  expect(valor, `${seletor} não declara ${propriedade}`).toBeDefined();
  return valor!;
}

// Cada par é o que uma tela de verdade desenha — o "quem está dentro de quem" vem
// de ler NovoCiclo.tsx, ImportarQTI.tsx, RelatorioAula.tsx, RelatorioCiclo.tsx e
// Acompanhamentos.tsx (ver comentário). `grande: true` = título ≥24px (piso 3:1);
// o resto é texto normal (piso 4,5:1).
const PARES: { desc: string; fg: string | null; bg: string | null; grande?: boolean }[] = [
  {
    desc: "Título h1/h2 — 'Começar um acompanhamento', 'Relatório da aula', etc. (todas as 5 telas)",
    fg: "h1, h2, h3", bg: null, grande: true,
  },
  {
    desc: "Texto corrido sobre a página — parágrafos, valor de índice, célula de tabela sem cor própria",
    fg: null, bg: null,
  },
  {
    desc: "Rótulo de campo — Turma, Disciplina, Relatório (CSV), datas (NovoCiclo, ImportarQTI)",
    fg: ".field__label", bg: null,
  },
  {
    desc: "Texto digitado/selecionado dentro do campo (NovoCiclo, ImportarQTI)",
    fg: ".field__input", bg: ".field__input",
  },
  {
    desc: "Metadado (.meta) solto sobre a página — datas, contagens (RelatorioAula, RelatorioCiclo, Acompanhamentos)",
    fg: ".meta", bg: null,
  },
  {
    desc: "Metadado (.meta) dentro de um item de lista em hover (RelatorioAula, RelatorioCiclo, Acompanhamentos)",
    fg: ".meta", bg: ".list__item:hover",
  },
  {
    desc: "Link 'Ver o acompanhamento' / 'Enviar o relatório do questionário', em repouso (Acompanhamentos)",
    fg: ".list__item a", bg: null,
  },
  {
    desc: "Mesmo link, com o item de lista em hover (Acompanhamentos)",
    fg: ".list__item a", bg: ".list__item:hover",
  },
  {
    desc: "Aviso (.banner) — erro/info/sucesso têm a mesma superfície, só a borda muda (todas as 5 telas)",
    fg: null, bg: ".banner",
  },
  {
    desc: "Botão primário — 'Começar', 'Enviar', 'Começar um acompanhamento' (NovoCiclo, ImportarQTI, Acompanhamentos)",
    fg: ".btn--primary", bg: ".btn--primary",
  },
  {
    desc: "Botão desabilitado — enquanto o formulário envia (NovoCiclo, ImportarQTI)",
    fg: ".btn:disabled", bg: ".btn:disabled",
  },
  {
    desc: "Título do estado vazio 'Nenhum acompanhamento ainda' (Acompanhamentos)",
    fg: "h1, h2, h3", bg: ".empty", grande: true,
  },
  {
    desc: "Parágrafo do estado vazio (Acompanhamentos)",
    fg: null, bg: ".empty",
  },
];

test.each(PARES)("$desc — dentro do limite e fora dos três pares proibidos", ({ fg, bg, grande }) => {
  const texto = corEfetiva(fg);
  const fundo = fundoEfetivo(bg);
  const piso = grande ? 3 : 4.5;
  expect(contraste(texto, fundo), `${texto} sobre ${fundo}`).toBeGreaterThanOrEqual(piso);

  const proibidos = TOKENS_JSON.forbidden_text_pairs.map(
    ([a, b]) => [TOKENS_JSON.color.brand[a], TOKENS_JSON.color.brand[b]] as const,
  );
  const eProibido = proibidos.some(
    ([a, b]) => (a === texto && b === fundo) || (a === fundo && b === texto),
  );
  expect(eProibido, `${texto} sobre ${fundo} é um dos Três Pares Proibidos`).toBe(false);
});

// A tabela de trajetória (RelatorioCiclo) é o ponto que o brief aponta como mais
// provável de problema. Por leitura de CSS ela não tem como falhar o piso de
// contraste — não declara cor nem fundo próprios, então cai no par "texto corrido
// sobre a página" já medido acima. O que este teste garante é exatamente essa
// premissa: se algum dia `.table th, .table td` ganhar uma cor própria, este
// teste quebra e avisa que o par precisa entrar em PARES acima.
test("a tabela de trajetória do ciclo não declara cor nem fundo próprios (herda o par já medido)", () => {
  const r = regra(".table th, .table td");
  expect(r.has("color"), ".table th, .table td ganhou uma declaração de color").toBe(false);
  expect(r.has("background"), ".table th, .table td ganhou uma declaração de background").toBe(false);
});
