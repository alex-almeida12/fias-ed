// @vitest-environment node
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { expect, test } from "vitest";
import type { FaixaIntervalo, FiasGrupo } from "../../api/types";
import {
  agruparConsecutivos,
  arredondarJanelaMs,
  CLASSE_POR_GRUPO,
  dizerDuracao,
  janelaNecessariaMs,
  janelarPorDominante,
  LARGURA_MINIMA_BLOCO_PX,
} from "./FaixaDeTempo";

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

// ---- Resumir a aula em trechos de tempo quando o bloco não cabe na tela.
//
// A medição que motivou isto foi feita em Chrome de verdade, rasterizando o
// SVG e lendo o pixel central de cada retângulo: jsdom não faz layout e não
// prova nada sobre geometria. O que se testa aqui é a REGRA — qual grupo cada
// trecho afirma, e que largura cada trecho terá numa dada largura de faixa.

const FAIXA_PX_CELULAR = 328; // 360px de celular menos o respiro de .page
// Medido em Chrome, rasterizando o SVG: a 2,90px o pixel central de um bloco
// ainda sai na cor de outro grupo; a partir de 3,00px acerta sempre. É um
// número de fora do código — comparar a geometria com LARGURA_MINIMA_BLOCO_PX
// seria comparar a constante com ela mesma, e baixá-la não quebraria nada.
const JOELHO_MEDIDO_PX = 3;
const FAIXA_PX_DESKTOP = 1120; // .page tem max-width 72rem menos o mesmo respiro

/**
 * Uma aula de 47min20 com a forma de aula de verdade: trechos expositivos
 * longos entremeados de pergunta, resposta e silêncio curtos. Gerador
 * determinista — é a MESMA aula usada na medição em navegador (947 intervalos
 * de 3s que viram 93 blocos, o menor com 0,346px numa faixa de 328px).
 */
function aulaRealista(): FaixaIntervalo[] {
  const passo = 3000;
  const totalMs = 2840 * 1000;
  const quantosIntervalos = Math.ceil(totalMs / passo);
  let semente = 1;
  const sorteia = () => ((semente = (semente * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);
  const duracao: Record<FiasGrupo, [number, number]> = {
    direta: [4, 34], indireta: [1, 8], estudante: [1, 10], "silêncio": [1, 6],
  };
  const proximo: Record<FiasGrupo, FiasGrupo[]> = {
    direta: ["direta", "indireta", "silêncio", "estudante"],
    indireta: ["estudante", "estudante", "direta", "silêncio"],
    estudante: ["indireta", "direta", "estudante", "silêncio"],
    "silêncio": ["direta", "indireta", "estudante", "direta"],
  };
  const categorias: FiasGrupo[] = [];
  let grupo: FiasGrupo = "direta";
  while (categorias.length < quantosIntervalos) {
    const [min, max] = duracao[grupo];
    const quantos = min + Math.floor(sorteia() * (max - min + 1));
    for (let i = 0; i < quantos && categorias.length < quantosIntervalos; i += 1) categorias.push(grupo);
    grupo = proximo[grupo][Math.floor(sorteia() * 4)];
  }
  return categorias.map((g, i) => ({ inicio_ms: i * passo, fim_ms: Math.min((i + 1) * passo, totalMs), grupo: g }));
}

const duracaoTotalDe = (faixa: FaixaIntervalo[]) => faixa.reduce((max, f) => Math.max(max, f.fim_ms), 0);

/** O que a tela desenharia numa dada largura, pelas mesmas contas do componente. */
function desenhado(faixa: FaixaIntervalo[], larguraPx: number): FaixaIntervalo[] {
  const blocos = agruparConsecutivos(faixa);
  const janela = janelaNecessariaMs(blocos, duracaoTotalDe(faixa), larguraPx);
  return janela > 0 ? agruparConsecutivos(janelarPorDominante(faixa, janela)) : blocos;
}

function fracaoPorGrupo(faixa: FaixaIntervalo[]): Map<FiasGrupo, number> {
  const total = faixa.reduce((soma, f) => soma + (f.fim_ms - f.inicio_ms), 0);
  const fracao = new Map<FiasGrupo, number>();
  for (const f of faixa) fracao.set(f.grupo, (fracao.get(f.grupo) ?? 0) + (f.fim_ms - f.inicio_ms) / total);
  return fracao;
}

test("o trecho é de tempo, não de contagem de blocos: a largura de cada trecho é previsível", () => {
  // Blocos de durações muito diferentes. Agregar "de 3 em 3 blocos" daria
  // trechos de 9s e de 114s lado a lado — a largura em tela voltaria a ser
  // imprevisível, que é justamente o defeito. Com trecho de tempo, todo
  // retângulo tem a mesma duração.
  const faixa: FaixaIntervalo[] = [
    { inicio_ms: 0, fim_ms: 3000, grupo: "direta" },
    { inicio_ms: 3000, fim_ms: 6000, grupo: "estudante" },
    { inicio_ms: 6000, fim_ms: 120000, grupo: "direta" },
    { inicio_ms: 120000, fim_ms: 123000, grupo: "silêncio" },
    { inicio_ms: 123000, fim_ms: 150000, grupo: "indireta" },
  ];
  const trechos = janelarPorDominante(faixa, 30000);
  expect(trechos.map((t) => t.fim_ms - t.inicio_ms)).toEqual([30000, 30000, 30000, 30000, 30000]);
});

test("o grupo do trecho é o de maior duração — não o primeiro, não o último, não o mais frequente", () => {
  // Estudante aparece 4 vezes (8s no total), direta aparece 1 vez (12s) e
  // silêncio fecha o trecho (2s). Quem domina o TEMPO é direta, que não é nem a
  // primeira, nem a última, nem a mais frequente em contagem.
  const faixa: FaixaIntervalo[] = [
    { inicio_ms: 0, fim_ms: 2000, grupo: "estudante" },
    { inicio_ms: 2000, fim_ms: 4000, grupo: "estudante" },
    { inicio_ms: 4000, fim_ms: 6000, grupo: "estudante" },
    { inicio_ms: 6000, fim_ms: 8000, grupo: "estudante" },
    { inicio_ms: 8000, fim_ms: 20000, grupo: "direta" },
    { inicio_ms: 20000, fim_ms: 22000, grupo: "silêncio" },
  ];
  expect(janelarPorDominante(faixa, 30000).map((t) => t.grupo)).toEqual(["direta"]);
});

test("empate vai para quem começou antes dentro do trecho, mesmo fora de ordem na lista", () => {
  // earliest_start é o mesmo desempate que fias_rules.json fixa para
  // transformar turnos em intervalos. Dois grupos com exatamente 6s cada: vence
  // o que começou antes NO TEMPO — e o terceiro caso mostra que é o tempo que
  // manda, não a ordem em que os itens chegaram na lista.
  const emOrdem: FaixaIntervalo[] = [
    { inicio_ms: 0, fim_ms: 6000, grupo: "direta" },
    { inicio_ms: 6000, fim_ms: 12000, grupo: "estudante" },
  ];
  expect(janelarPorDominante(emOrdem, 30000).map((t) => t.grupo)).toEqual(["direta"]);
  const trocado: FaixaIntervalo[] = [
    { inicio_ms: 0, fim_ms: 6000, grupo: "estudante" },
    { inicio_ms: 6000, fim_ms: 12000, grupo: "direta" },
  ];
  expect(janelarPorDominante(trocado, 30000).map((t) => t.grupo)).toEqual(["estudante"]);
  const foraDeOrdem: FaixaIntervalo[] = [
    { inicio_ms: 6000, fim_ms: 12000, grupo: "estudante" },
    { inicio_ms: 0, fim_ms: 6000, grupo: "direta" },
  ];
  expect(janelarPorDominante(foraDeOrdem, 30000).map((t) => t.grupo)).toEqual(["direta"]);
});

test("um buraco na linha do tempo continua sem tinta depois de resumir", () => {
  // Nada foi dito entre 10s e 50s, e nada depois de 1min. O vão não pode ganhar
  // cor, e — de propósito — as pontas do que foi dito não caem nas bordas dos
  // trechos: o retângulo tem que ir de onde o dado começa até onde o dado acaba,
  // nunca até a borda do trecho, senão a faixa pinta tempo sobre o qual o motor
  // não disse nada (inclusive depois do fim da aula, no último trecho).
  const faixa: FaixaIntervalo[] = [
    { inicio_ms: 0, fim_ms: 10000, grupo: "direta" },
    { inicio_ms: 50000, fim_ms: 70000, grupo: "estudante" },
  ];
  expect(janelarPorDominante(faixa, 30000)).toEqual([
    { inicio_ms: 0, fim_ms: 10000, grupo: "direta" },
    { inicio_ms: 50000, fim_ms: 60000, grupo: "estudante" },
    { inicio_ms: 60000, fim_ms: 70000, grupo: "estudante" },
  ]);
});

test("todo retângulo desenhado tem pelo menos a largura mínima medida em navegador", () => {
  // O joelho medido em Chrome é 3,00px (o pixel do meio ainda erra a cor a
  // 2,90px); LARGURA_MINIMA_BLOCO_PX é 4. Este teste guarda que a conta do
  // componente entrega o que a medição exige, em toda largura plausível.
  expect(LARGURA_MINIMA_BLOCO_PX).toBeGreaterThanOrEqual(JOELHO_MEDIDO_PX);
  const faixa = aulaRealista();
  const total = duracaoTotalDe(faixa);
  for (const larguraPx of [FAIXA_PX_CELULAR, 480, 788, FAIXA_PX_DESKTOP]) {
    const maisEstreito = desenhado(faixa, larguraPx)
      .map((b) => ((b.fim_ms - b.inicio_ms) / total) * larguraPx)
      .reduce((min, px) => Math.min(min, px), Infinity);
    expect(maisEstreito, `faixa de ${larguraPx}px`).toBeGreaterThanOrEqual(JOELHO_MEDIDO_PX);
  }
});

test("nenhum grupo com fatia relevante da aula some da faixa", () => {
  // Resumir por dominante pode calar um grupo que só aparece em rajadas curtas.
  // A exigência: quem ocupa 5% ou mais da aula continua aparecendo na tela.
  const faixa = aulaRealista();
  const relevantes = [...fracaoPorGrupo(faixa)].filter(([, f]) => f >= 0.05).map(([grupo]) => grupo);
  expect(relevantes.length, "a aula de teste precisa ter vários grupos relevantes").toBeGreaterThan(2);
  for (const larguraPx of [FAIXA_PX_CELULAR, FAIXA_PX_DESKTOP]) {
    const naTela = new Set(desenhado(faixa, larguraPx).map((b) => b.grupo));
    const sumiram = relevantes.filter((grupo) => !naTela.has(grupo));
    expect(sumiram, `grupos relevantes que somem numa faixa de ${larguraPx}px`).toEqual([]);
  }
});

test("resumir não inventa grupo que a aula não teve", () => {
  const faixa = aulaRealista().filter((f) => f.grupo !== "indireta");
  const existentes = new Set(faixa.map((f) => f.grupo));
  for (const b of desenhado(faixa, FAIXA_PX_CELULAR)) expect(existentes.has(b.grupo)).toBe(true);
});

test("numa tela em que todo bloco já cabe, a faixa não resume nada", () => {
  // Afirmar o grupo de cada instante é a afirmação mais forte: só se abre mão
  // dela quando a tela não a comporta.
  const cabe: FaixaIntervalo[] = [
    { inicio_ms: 0, fim_ms: 60000, grupo: "direta" },
    { inicio_ms: 60000, fim_ms: 120000, grupo: "estudante" },
  ];
  expect(janelaNecessariaMs(agruparConsecutivos(cabe), 120000, FAIXA_PX_CELULAR)).toBe(0);
  // E sem largura medida (primeira pintura, e jsdom, que não faz layout)
  // também não se resume nada: só se resume o que se mediu.
  expect(janelaNecessariaMs(agruparConsecutivos(aulaRealista()), 2840000, 0)).toBe(0);
});

test("a duração do trecho é arredondada para cima, nunca para baixo", () => {
  // Arredondar para baixo devolveria trechos abaixo da largura mínima — o
  // defeito de volta, por um erro de arredondamento.
  for (const ms of [1, 4999, 10100, 34630, 59000, 60001, 130000]) {
    expect(arredondarJanelaMs(ms), `${ms}ms`).toBeGreaterThanOrEqual(ms);
  }
  expect(arredondarJanelaMs(34630)).toBe(35000);
  expect(arredondarJanelaMs(10140)).toBe(15000);
});

test("a frase da tela diz a duração em português, sem jargão", () => {
  expect(dizerDuracao(35000)).toBe("35 segundos");
  expect(dizerDuracao(60000)).toBe("1 minuto");
  expect(dizerDuracao(90000)).toBe("1 minuto e 30 segundos");
  expect(dizerDuracao(120000)).toBe("2 minutos");
  for (const ms of [15000, 45000, 90000, 300000]) {
    expect(dizerDuracao(ms)).not.toMatch(/pixel|janela|agrega|renderiz|avalia|nota|desempenho|ranking/i);
  }
});
