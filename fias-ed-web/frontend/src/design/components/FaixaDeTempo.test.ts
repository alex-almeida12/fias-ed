// @vitest-environment node
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { expect, test } from "vitest";
import type { FaixaIntervalo, FiasGrupo } from "../../api/types";
import { agruparConsecutivos, CLASSE_POR_GRUPO } from "./FaixaDeTempo";

// Estes testes leem o CSS de verdade em vez de repetir as cores aqui: um teste
// que compara uma constante do módulo com a mesma constante copiada para o
// teste passa mesmo com o componente quebrado. A fonte da cor é o CSS, então é
// o CSS que é medido.
const ler = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), "utf8");
const TOKENS = ler("../../../../../fias-ed-shared/design-tokens/build/tokens.css");
const COMPONENTES = ler("../components.css");

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

/** As declarações de uma regra do components.css, pelo seletor exato. */
function regra(seletor: string): Map<string, string> {
  const abre = COMPONENTES.indexOf(`${seletor} {`);
  expect(abre, `regra ${seletor} não existe em components.css`).toBeGreaterThan(-1);
  const corpo = COMPONENTES.slice(abre + seletor.length + 2, COMPONENTES.indexOf("}", abre));
  return new Map(
    corpo
      .split(";")
      .filter((d) => d.includes(":"))
      .map((d) => [d.slice(0, d.indexOf(":")).trim(), d.slice(d.indexOf(":") + 1).trim()]),
  );
}

function declaracao(seletor: string, propriedade: string): string {
  const valor = regra(seletor).get(propriedade);
  expect(valor, `${seletor} não declara ${propriedade}`).toBeDefined();
  return valor!;
}

// Contraste do WCAG 2.1 (relação entre luminâncias relativas, 1.4.11 pede 3:1
// para elemento gráfico que carrega informação).
function luminancia(cor: string): number {
  const canais = [1, 3, 5].map((i) => parseInt(cor.slice(i, i + 2), 16) / 255);
  const [r, g, b] = canais.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contraste(a: string, b: string): number {
  const [claro, escuro] = [luminancia(a), luminancia(b)].sort((x, y) => y - x);
  return (claro + 0.05) / (escuro + 0.05);
}

const GRUPOS = Object.keys(CLASSE_POR_GRUPO) as FiasGrupo[];
const preenchimento = (g: FiasGrupo) => hex(declaracao(`.faixa-tempo__seg--${CLASSE_POR_GRUPO[g]}`, "fill"));
const contorno = (g: FiasGrupo) => hex(declaracao(`.faixa-tempo__seg--${CLASSE_POR_GRUPO[g]}`, "stroke"));

test("a espessura do contorno é em pixel de tela, não em unidade do viewBox", () => {
  // O viewBox da faixa é 0 0 <duração em ms> 1: a escala é absurdamente não
  // uniforme. Sem non-scaling-stroke, 1 unidade de espessura vira uma fração
  // de pixel nas arestas verticais (as fronteiras somem) e a altura inteira da
  // barra nas horizontais (a faixa fica de uma cor só). Só o navegador mostra
  // isso de verdade — aqui fica o guarda de que a declaração não sumiu.
  expect(declaracao(".faixa-tempo__seg", "vector-effect")).toBe("non-scaling-stroke");
  expect(declaracao(".faixa-tempo__seg", "stroke-width")).toBe("var(--border-hairline)");
});

test("a régua de contraste bate com a do WCAG em pares conhecidos", () => {
  // Sem isto, um erro na fórmula faria todos os testes abaixo passarem por engano.
  expect(contraste("#FFFFFF", "#000000")).toBeCloseTo(21, 2);
  expect(contraste("#2F4156", "#FFFFFF")).toBeCloseTo(10.44, 1); // navy x branco
  expect(contraste("#567C8D", "#2F4156")).toBeCloseTo(2.32, 1); // teal x navy: o par que obriga o contorno
});

test("dois dos seis pares de preenchimento não se separam sozinhos — é por isso que há contorno", () => {
  // O motivo do contorno existir, escrito como medida e não como comentário:
  // se algum dia a paleta mudar e os quatro preenchimentos passarem a se
  // separar sozinhos, este teste falha e avisa que o contorno virou enfeite.
  const abaixoDe3 = [];
  for (const [i, a] of GRUPOS.entries()) {
    for (const b of GRUPOS.slice(i + 1)) {
      if (contraste(preenchimento(a), preenchimento(b)) < 3) abaixoDe3.push(`${a} x ${b}`);
    }
  }
  expect(abaixoDe3).toEqual(["indireta x direta", "estudante x silêncio"]);
});

test("todo par de grupos vizinhos se separa: pelos preenchimentos ou por um contorno de 3:1 contra os dois", () => {
  // Nos quatro pares que já se separam sozinhos (claro contra escuro) não há
  // nada a exigir do contorno — e não haveria como exigir: separar dois
  // preenchimentos que distam menos de 9:1 entre si com uma terceira cor a 3:1
  // de cada um é aritmeticamente impossível, e teal x sky, por exemplo, dista
  // 3,11:1. Nos dois pares que não se separam, a exigência vale inteira, e
  // vale para os dois contornos: os retângulos encostam, os dois contornos de
  // 1px ficam centrados na mesma aresta e qual deles sobra por cima depende da
  // ordem de pintura. Exigir dos dois é o que torna a fronteira independente
  // disso — e é o que derruba qualquer contorno de cor única (branco some
  // entre sky e bege, navy some entre teal e navy).
  const falhas: string[] = [];
  for (const [i, a] of GRUPOS.entries()) {
    for (const b of GRUPOS.slice(i + 1)) {
      if (contraste(preenchimento(a), preenchimento(b)) >= 3) continue;
      for (const dono of [a, b]) {
        const linha = contorno(dono);
        const separa = contraste(linha, preenchimento(a)) >= 3 && contraste(linha, preenchimento(b)) >= 3;
        if (!separa) falhas.push(`${a} x ${b} com o contorno de ${dono} por cima`);
      }
    }
  }
  expect(falhas, "fronteiras sem contorno que se separe dos dois preenchimentos").toEqual([]);
});

test("cada quadradinho da legenda se separa da superfície branca", () => {
  const superficie = hex("var(--color-surface)");
  const falhas: string[] = [];
  for (const grupo of GRUPOS) {
    const seletor = `.faixa-tempo-legenda__marca--${CLASSE_POR_GRUPO[grupo]}`;
    const fundo = hex(declaracao(seletor, "background"));
    const borda = hex(declaracao(seletor, "border-color"));
    // Ou o preenchimento já se vê contra o branco, ou a borda o desenha.
    const visivel = contraste(fundo, superficie) >= 3 || contraste(borda, superficie) >= 3;
    if (!visivel) falhas.push(`${grupo} (fundo ${fundo}, borda ${borda})`);
  }
  expect(falhas, "quadradinhos invisíveis sobre a superfície").toEqual([]);
});

test("a legenda usa a mesma dupla preenchimento/contorno que a faixa", () => {
  for (const grupo of GRUPOS) {
    const seletor = `.faixa-tempo-legenda__marca--${CLASSE_POR_GRUPO[grupo]}`;
    expect(hex(declaracao(seletor, "background"))).toBe(preenchimento(grupo));
    expect(hex(declaracao(seletor, "border-color"))).toBe(contorno(grupo));
  }
});

const intervalo = (inicio: number, grupo: FiasGrupo): FaixaIntervalo => ({ inicio_ms: inicio, fim_ms: inicio + 3000, grupo });

test("intervalos consecutivos do mesmo grupo viram um retângulo só", () => {
  const minutoContinuo = Array.from({ length: 20 }, (_, i) => intervalo(i * 3000, "indireta"));
  expect(agruparConsecutivos(minutoContinuo)).toEqual([{ inicio_ms: 0, fim_ms: 60000, grupo: "indireta" }]);
});

test("grupos diferentes não são fundidos, e os tempos são os das pontas", () => {
  const faixa = [
    intervalo(0, "indireta"),
    intervalo(3000, "indireta"),
    intervalo(6000, "direta"),
    intervalo(9000, "estudante"),
    intervalo(12000, "silêncio"),
    intervalo(15000, "silêncio"),
  ];
  expect(agruparConsecutivos(faixa)).toEqual([
    { inicio_ms: 0, fim_ms: 6000, grupo: "indireta" },
    { inicio_ms: 6000, fim_ms: 9000, grupo: "direta" },
    { inicio_ms: 9000, fim_ms: 12000, grupo: "estudante" },
    { inicio_ms: 12000, fim_ms: 18000, grupo: "silêncio" },
  ]);
});

test("um buraco na linha do tempo não vira tinta contínua", () => {
  // Mesmo grupo dos dois lados, mas com um vão no meio: são dois retângulos,
  // senão a faixa pintaria tempo sobre o qual não se disse nada.
  const faixa = [intervalo(0, "direta"), intervalo(30000, "direta")];
  expect(agruparConsecutivos(faixa)).toHaveLength(2);
});

test("juntar não muda a duração total nem a duração de cada grupo", () => {
  const faixa = Array.from({ length: 900 }, (_, i) => intervalo(i * 3000, GRUPOS[Math.floor(i / 7) % 4]));
  const somaPorGrupo = (lista: FaixaIntervalo[]) => {
    const soma = new Map<FiasGrupo, number>();
    for (const f of lista) soma.set(f.grupo, (soma.get(f.grupo) ?? 0) + (f.fim_ms - f.inicio_ms));
    return [...soma].sort();
  };
  expect(somaPorGrupo(agruparConsecutivos(faixa))).toEqual(somaPorGrupo(faixa));
});
