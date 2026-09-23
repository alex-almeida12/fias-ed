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
  const blocos = agruparConsecutivos(faixa);

  return (
    <>
      {/* O resumo em palavras sai da faixa original, não dos blocos: juntar
         intervalos vizinhos não muda nenhuma duração, mas a soma é do dado. */}
      <svg className="faixa-tempo" viewBox={`0 0 ${duracaoTotal} 1`} preserveAspectRatio="none"
        role="img" aria-label={`Distribuição da fala ao longo da aula: ${resumoTextual(faixa)}.`}>
        {blocos.map((b) => (
          <rect key={b.inicio_ms} x={b.inicio_ms} y={0} width={Math.max(b.fim_ms - b.inicio_ms, 1)} height={1}
            data-grupo={CLASSE_POR_GRUPO[b.grupo]}
            className={`faixa-tempo__seg faixa-tempo__seg--${CLASSE_POR_GRUPO[b.grupo]}`} />
        ))}
      </svg>
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
