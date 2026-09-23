import type { FaixaIntervalo, FiasGrupo } from "../../api/types";

// As quatro cores que fias-ed-shared/design-tokens/tokens.json já reserva
// para os grupos FIAS (indirect/direct/student/silence → --color-fias-*,
// DESIGN.md). O nome da classe é o mesmo nome em português que a API devolve
// em `grupo`, sem acento (CSS não aceita "í" numa classe sem escapar).
const CLASSE_POR_GRUPO: Record<FiasGrupo, string> = {
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

// As quatro cores de grupo não se separam sozinhas: indireta (teal) contra
// direta (navy) dá 2,32:1 e estudante (sky) contra silêncio (bege) dá 1,27:1 —
// os dois abaixo dos 3:1 que o WCAG 1.4.11 exige de uma fronteira gráfica que
// carrega informação, e são as duas adjacências mais comuns numa aula real
// (o professor alternando indireta/direta; um turno de aluno seguido de
// silêncio). Nenhum separador de cor única cobre as quatro cores ao mesmo
// tempo (branco falha contra sky e bege; navy falha contra teal e contra si
// mesmo) — por isso o contorno é por grupo, não uma cor fixa: os dois grupos
// escuros (indireta/teal, direta/navy) recebem contorno branco (4,50:1 e
// 10,44:1); os dois claros (estudante/sky, silêncio/bege) recebem contorno
// navy (7,22:1 e 9,16:1). Assim toda fronteira entre dois grupos quaisquer
// tem pelo menos um lado com contorno que contrasta com os dois vizinhos.
const CONTORNO_POR_GRUPO: Record<FiasGrupo, string> = {
  indireta: "var(--color-white)",
  direta: "var(--color-white)",
  estudante: "var(--color-navy)",
  "silêncio": "var(--color-navy)",
};

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

  return (
    <>
      <svg className="faixa-tempo" viewBox={`0 0 ${duracaoTotal} 1`} preserveAspectRatio="none"
        role="img" aria-label={`Distribuição da fala ao longo da aula: ${resumoTextual(faixa)}.`}>
        {faixa.map((f) => (
          <rect key={f.inicio_ms} x={f.inicio_ms} y={0} width={Math.max(f.fim_ms - f.inicio_ms, 1)} height={1}
            data-grupo={CLASSE_POR_GRUPO[f.grupo]} stroke={CONTORNO_POR_GRUPO[f.grupo]} strokeWidth={1}
            // O viewBox está em milissegundos (eixo x) contra uma unidade só (eixo
            // y) — vector-effect faz a espessura do contorno ficar em pixels de
            // tela de verdade, e não distorcer com essa escala não uniforme.
            vectorEffect="non-scaling-stroke"
            className={`faixa-tempo__seg faixa-tempo__seg--${CLASSE_POR_GRUPO[f.grupo]}`} />
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
