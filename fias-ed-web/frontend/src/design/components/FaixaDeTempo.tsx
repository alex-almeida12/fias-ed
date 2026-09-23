import { useEffect, useMemo, useRef, useState } from "react";
import type { FaixaIntervalo, FiasGrupo } from "../../api/types";

// As quatro cores que fias-ed-shared/design-tokens/tokens.json já reserva
// para os grupos FIAS (indirect/direct/student/silence → --color-fias-*,
// DESIGN.md). O nome da classe é o mesmo nome em português que a API devolve
// em `grupo`, sem acento (CSS não aceita "í" numa classe sem escapar).
// A cor de preenchimento e a cor de contorno de cada grupo vivem no CSS
// (`.faixa-tempo__seg--*` em components.css), onde já morava o `fill`: a mesma
// cor do mesmo elemento não é declarada em dois lugares.
export const CLASSE_POR_GRUPO: Record<FiasGrupo, string> = {
  indireta: "indireta",
  direta: "direta",
  estudante: "estudante",
  "silêncio": "silencio",
};

const NOME_POR_GRUPO: Record<FiasGrupo, string> = {
  indireta: "influência indireta do professor",
  direta: "influência direta do professor",
  estudante: "fala dos estudantes",
  "silêncio": "silêncio ou confusão",
};

// O backend manda um item por intervalo de codificação FIAS, e fias_rules.json
// fixa esse intervalo em 3s: uma aula de 45 min chega aqui com 900 itens. Um
// <rect> por item quebra a faixa de duas maneiras.
//
// A primeira é geométrica: a faixa tem no máximo ~1120px no desktop e ~328px
// num celular de 360px, então 900 retângulos dão 1,24px e 0,36px de largura. O
// contorno de 1px é centrado na aresta e come 0,5px de cada lado, de modo que
// o preenchimento visível seria 0,24px no desktop e zero no celular — as
// quatro cores de grupo colapsariam nas duas cores de contorno, e a parte de
// fala docente ficaria branca sobre o fundo branco (1:1).
//
// A segunda é de honestidade do gráfico: o contorno desenharia uma fronteira a
// cada 3s, inclusive entre dois intervalos do mesmo grupo. Um minuto contínuo
// de influência indireta apareceria como 20 blocos separados, afirmando uma
// granularidade de turno que o dado não tem. O WCAG 1.4.11 pede fronteira
// perceptível entre grupos, não em todo lugar.
//
// Juntar intervalos vizinhos e contíguos do mesmo grupo resolve as duas: a
// aula de 45 min cai para algumas dezenas de retângulos, cada um com largura
// de sobra para o contorno, e cada contorno cai numa mudança de grupo real.
// Isto é apresentação, não classificação — quem decide a categoria de cada
// intervalo continua sendo o motor, no backend.
export function agruparConsecutivos(faixa: FaixaIntervalo[]): FaixaIntervalo[] {
  const blocos: FaixaIntervalo[] = [];
  for (const intervalo of faixa) {
    const ultimo = blocos[blocos.length - 1];
    // Só funde o que é do mesmo grupo E encosta no anterior: um buraco na
    // linha do tempo é um fato, não pode virar tinta contínua.
    if (ultimo && ultimo.grupo === intervalo.grupo && ultimo.fim_ms === intervalo.inicio_ms) {
      blocos[blocos.length - 1] = { ...ultimo, fim_ms: intervalo.fim_ms };
    } else {
      blocos.push({ ...intervalo });
    }
  }
  return blocos;
}

// Juntar intervalos vizinhos resolve o contorno, mas não resolve a aritmética
// da tela. Numa aula de 47min20 medida em Chrome de verdade, a 328px (o que
// sobra de um celular de 360px depois do respiro da página), os 93 blocos
// juntados têm 0,346px no menor e 36 deles ficam abaixo de 2px. Nessa largura o
// navegador não tem pixel com que dizer a cor do bloco: ele mistura o bloco com
// os vizinhos e com os contornos, e o pixel do meio sai na cor de OUTRO grupo
// em 33 dos 93 blocos (12 dos 93 a 1120px). Bege virando navy não é perda de
// nitidez — é a tela afirmando "aqui o professor falou de forma direta" sobre
// um trecho de silêncio. Num produto que promete descrever a aula com
// honestidade, isso é defeito de correção, não de estética.
//
// A largura mínima abaixo saiu de medição, não de estimativa: varrendo larguras
// uniformes em Chrome, com as adjacências piores (claro entre escuros e
// vice-versa) e com deslocamentos fracionários, o pixel do meio ainda erra a
// cor a 2,90px e acerta sempre a partir de 3,00px — em faixa de 328px e de
// 1120px, igual. O número tem explicação estrutural: o contorno de 1px fica
// centrado na aresta e come 0,5px de cada lado, então 3px de bloco garantem 2px
// de preenchimento, e 2px de preenchimento contêm um pixel inteiro qualquer que
// seja o deslocamento. Fica 4px para não trabalhar em cima do joelho da curva.
export const LARGURA_MINIMA_BLOCO_PX = 4;

/** Quanto tempo de aula ocupa a largura mínima, nesta largura de faixa. */
export function duracaoMinimaVisivelMs(duracaoTotalMs: number, larguraPx: number): number {
  return (LARGURA_MINIMA_BLOCO_PX / larguraPx) * duracaoTotalMs;
}

/**
 * Arredonda para cima até uma duração que dá para dizer em voz alta na tela —
 * múltiplo de 5s até um minuto, de 30s daí para cima. Para cima porque
 * arredondar para baixo devolveria trechos abaixo do mínimo; e sem arredondar,
 * o número dito na tela mudaria a cada pixel de redimensionamento.
 */
export function arredondarJanelaMs(ms: number): number {
  const segundos = Math.ceil(ms / 1000);
  const passo = segundos <= 60 ? 5 : 30;
  return Math.ceil(segundos / passo) * passo * 1000;
}

/**
 * Abaixo da largura mínima a faixa para de afirmar o grupo de cada instante e
 * passa a afirmar o grupo que DE FATO domina cada trecho de tempo de tamanho
 * fixo. O trecho é de tempo, não de contagem de blocos: os blocos têm durações
 * muito diferentes, então "de 3 em 3 blocos" não daria largura previsível — e o
 * que precisa ser previsível aqui é justamente a largura desenhada.
 *
 * Dominante é o grupo de MAIOR DURAÇÃO somada dentro do trecho: não o primeiro,
 * não o último, não o mais frequente em contagem. Empate vai para o que começou
 * antes dentro do trecho. Não é critério inventado aqui — é o mesmo par
 * `largest_coverage` + `earliest_start` que fias_rules.json já fixa para
 * transformar turnos em intervalos: a tela resume tempo com a mesma regra com
 * que o motor resume tempo.
 *
 * Isto continua sendo apresentação, não classificação: quem decide a categoria
 * de cada intervalo é o motor, no backend. A faixa só escolhe, entre o que o
 * motor decidiu, o que ela consegue desenhar sem afirmar coisa errada.
 */
export function janelarPorDominante(faixa: FaixaIntervalo[], janelaMs: number): FaixaIntervalo[] {
  const fimDaAula = faixa.reduce((max, f) => Math.max(max, f.fim_ms), 0);
  const trechos: FaixaIntervalo[] = [];
  for (let abre = 0; abre < fimDaAula; abre += janelaMs) {
    const fecha = abre + janelaMs;
    const duracao = new Map<FiasGrupo, number>();
    const comeco = new Map<FiasGrupo, number>();
    let de = Infinity;
    let ate = -Infinity;
    for (const f of faixa) {
      const a = Math.max(f.inicio_ms, abre);
      const b = Math.min(f.fim_ms, fecha);
      if (b <= a) continue;
      duracao.set(f.grupo, (duracao.get(f.grupo) ?? 0) + (b - a));
      if (!comeco.has(f.grupo)) comeco.set(f.grupo, a);
      de = Math.min(de, a);
      ate = Math.max(ate, b);
    }
    // Trecho sobre o qual o motor não disse nada continua sem tinta, e o
    // retângulo vai só de onde começa até onde acaba o que foi dito, nunca até
    // a borda do trecho: um buraco na linha do tempo é um fato.
    if (ate <= de) continue;
    let dominante: FiasGrupo | null = null;
    for (const [grupo, ms] of duracao) {
      if (dominante === null) {
        dominante = grupo;
        continue;
      }
      const atual = duracao.get(dominante) ?? 0;
      if (ms > atual || (ms === atual && (comeco.get(grupo) ?? 0) < (comeco.get(dominante) ?? 0))) dominante = grupo;
    }
    trechos.push({ inicio_ms: de, fim_ms: ate, grupo: dominante! });
  }
  return trechos;
}

/**
 * Quanto tempo cabe em cada trecho desenhado nesta largura — 0 quando não é
 * preciso resumir nada. Resumir só quando precisa é parte do conserto: numa
 * tela em que todo bloco do dado já se desenha na própria cor, a faixa continua
 * afirmando o grupo de cada instante, que é a afirmação mais forte possível.
 */
export function janelaNecessariaMs(blocos: FaixaIntervalo[], duracaoTotalMs: number, larguraPx: number): number {
  if (blocos.length === 0 || duracaoTotalMs <= 0 || larguraPx <= 0) return 0;
  const minimoMs = duracaoMinimaVisivelMs(duracaoTotalMs, larguraPx);
  const menorBlocoMs = blocos.reduce((min, b) => Math.min(min, b.fim_ms - b.inicio_ms), Infinity);
  if (menorBlocoMs >= minimoMs) return 0;
  return Math.min(arredondarJanelaMs(minimoMs), duracaoTotalMs);
}

/** "35 segundos", "1 minuto", "1 minuto e 30 segundos" — para dizer na tela. */
export function dizerDuracao(ms: number): string {
  const segundos = Math.round(ms / 1000);
  const minutos = Math.floor(segundos / 60);
  const resto = segundos % 60;
  if (minutos === 0) return `${resto} segundos`;
  const parteMinutos = minutos === 1 ? "1 minuto" : `${minutos} minutos`;
  return resto === 0 ? parteMinutos : `${parteMinutos} e ${resto} segundos`;
}

// Cor nunca pode ser o único portador de significado (DESIGN.md): esta função
// escreve em palavras a mesma distribuição que as barras mostram, para o
// aria-label do gráfico — não uma legenda decorativa, é a alternativa textual.
function resumoTextual(faixa: FaixaIntervalo[]): string {
  const duracaoTotal = faixa.reduce((soma, f) => soma + (f.fim_ms - f.inicio_ms), 0);
  if (duracaoTotal <= 0) return "sem dados de duração para esta aula";
  const duracaoPorGrupo = new Map<FiasGrupo, number>();
  for (const f of faixa) duracaoPorGrupo.set(f.grupo, (duracaoPorGrupo.get(f.grupo) ?? 0) + (f.fim_ms - f.inicio_ms));
  const ordem: FiasGrupo[] = ["indireta", "direta", "estudante", "silêncio"];
  return ordem
    .filter((grupo) => (duracaoPorGrupo.get(grupo) ?? 0) > 0)
    .map((grupo) => `${Math.round(((duracaoPorGrupo.get(grupo) ?? 0) / duracaoTotal) * 100)}% de ${NOME_POR_GRUPO[grupo]}`)
    .join(", ");
}

type Props = { faixa: FaixaIntervalo[] };

export function FaixaDeTempo({ faixa }: Props) {
  const duracaoTotal = faixa.reduce((max, f) => Math.max(max, f.fim_ms), 0) || 1;

  // A faixa é `width: 100%`: quem manda na largura é o contêiner, não a janela
  // do navegador. Por isso medimos o elemento e reagimos quando ele muda — um
  // `window.innerWidth` fixo erraria dentro de qualquer coluna e não reagiria a
  // girar o celular. Enquanto a largura é desconhecida (primeira pintura, e
  // jsdom, que não faz layout nem tem ResizeObserver), a faixa desenha o dado
  // intervalo a intervalo: só se resume o que se mediu.
  const svgRef = useRef<SVGSVGElement>(null);
  const [larguraPx, setLarguraPx] = useState(0);
  useEffect(() => {
    const elemento = svgRef.current;
    if (!elemento || typeof ResizeObserver === "undefined") return;
    setLarguraPx(elemento.getBoundingClientRect().width);
    const observador = new ResizeObserver(([entrada]) => setLarguraPx(entrada.contentRect.width));
    observador.observe(elemento);
    return () => observador.disconnect();
  }, []);

  const blocos = useMemo(() => agruparConsecutivos(faixa), [faixa]);
  const janelaMs = janelaNecessariaMs(blocos, duracaoTotal, larguraPx);
  const desenhados = useMemo(
    () => (janelaMs > 0 ? agruparConsecutivos(janelarPorDominante(faixa, janelaMs)) : blocos),
    [faixa, blocos, janelaMs],
  );

  return (
    <>
      {/* O resumo em palavras sai da faixa ORIGINAL, não dos blocos nem dos
         trechos resumidos: juntar e resumir não mudam nenhuma duração, e é a
         alternativa textual que carrega a porcentagem exata de cada grupo —
         ela não perde resolução em tela nenhuma. */}
      <svg ref={svgRef} className="faixa-tempo" viewBox={`0 0 ${duracaoTotal} 1`} preserveAspectRatio="none"
        role="img" aria-label={`Distribuição da fala ao longo da aula: ${resumoTextual(faixa)}.`}>
        {desenhados.map((b) => (
          <rect key={b.inicio_ms} x={b.inicio_ms} y={0} width={Math.max(b.fim_ms - b.inicio_ms, 1)} height={1}
            data-grupo={CLASSE_POR_GRUPO[b.grupo]}
            className={`faixa-tempo__seg faixa-tempo__seg--${CLASSE_POR_GRUPO[b.grupo]}`} />
        ))}
      </svg>
      {/* Quando a faixa deixa de mostrar instante a instante, ela diz o que
         passou a mostrar: quem lê uma cor no minuto 12 precisa saber a que
         pedaço de aula aquela cor se refere. */}
      {janelaMs > 0 && (
        <p className="faixa-tempo__nota">
          Cada trecho de cor mostra o que mais apareceu em cada {dizerDuracao(janelaMs)} de aula.
        </p>
      )}
      <ul className="faixa-tempo-legenda">
        {(Object.keys(CLASSE_POR_GRUPO) as FiasGrupo[]).map((grupo) => (
          <li key={grupo} className="faixa-tempo-legenda__item">
            <span aria-hidden="true" className={`faixa-tempo-legenda__marca faixa-tempo-legenda__marca--${CLASSE_POR_GRUPO[grupo]}`} />
            {NOME_POR_GRUPO[grupo]}
          </li>
        ))}
      </ul>
    </>
  );
}
