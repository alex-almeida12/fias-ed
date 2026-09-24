"""Segmentos codificados + evidência de fala → marcas de codificação FIAS e
matriz de transições.

Três segundos é a taxa MÍNIMA de amostragem do protocolo, não um balde em que a
categoria dominante vence. Flanders (1970):

  regra 3 — "If more than one category is active in a span of 3 seconds, all the
  categories should be recorded. If after 3 seconds, no category changes, then
  the same serial number should be repeated."

  regra 4 — "If the time period of silence exceeds 3 seconds, it should be
  recorded under the category No.10"

A leitura de balde ("uma marca por intervalo de 3 s, vence quem cobre mais")
destrói justamente o que a matriz 10×10 existe para exibir: medida numa aula
real de 24 min, ela capturava 102 das 138 mudanças de categoria da linha do
tempo (73,9%), e 5 dos 213 segmentos sumiam por completo da saída por não
vencerem balde nenhum.

Aqui a linha do tempo é resolvida instante a instante e só depois amostrada:
toda mudança de categoria vira marca, e dentro de um trecho de categoria
constante repete-se a marca a cada 3 s. O relógio dos 3 s REINICIA a cada
mudança (`interval_coding.clock = "restart_on_change"`), leitura literal da
regra 3 — o "if after 3 seconds, no category changes" conta a partir do último
registro, não de uma grade fixa em 0, 3, 6 s. Consequência prática: a sequência
é invariante a onde a gravação começou; cortar 1 s da frente da aula não
redistribui as marcas, como aconteceria com grade global.

A não-fala vem do DIARIZADOR, nunca das lacunas entre segmentos do ASR. O
`vad_filter` do Whisper cola as pausas para dentro dos segmentos: na mesma aula,
as lacunas entre segmentos do ASR somam 21,5 s (20 das 21 abaixo de 3 s),
enquanto as lacunas entre turnos do diarizador somam 78,2 s em 18 lacunas de 3 s
ou mais — 5,4% da aula. Medir silêncio pelo ASR mede o VAD do ASR, não a aula.
Por isso `speech` entra na assinatura: a evidência de fala/não-fala é insumo, e
não algo que se possa derivar dos segmentos já codificados.

A categoria 10 é "silêncio OU confusão", e aqui ela recebe SÓ silêncio
(`confusion.implemented = false`). Confusão, na definição original, é
"communication cannot be understood by the observer": exige sobreposição de
falantes E inintelegibilidade. Sobreposição sozinha é participação normal de
sala de aula — gente fala por cima e se entende —, e marcá-la como confusão
inverteria o significado de um sinal que costuma ser de engajamento. O sinal de
inintelegibilidade (a confiança de decodificação do ASR) não chega até aqui
hoje. Enquanto não chegar, este motor não inventa confusão.

O que ele GARANTE é que os dois não sejam trocados um pelo outro, que é o pior
erro possível entre dois fenômenos acústicos opostos: fala que o diarizador
ouviu e o ASR não transcreveu não vira silêncio, porque silêncio é ausência de
fala segundo o diarizador. Ela é absorvida pela categoria em curso, como
qualquer trecho sem categoria própria.
"""
from dataclasses import dataclass

# Origem de cada trecho da linha do tempo. Só "silence" é contabilizado em
# Coding: "carry" é o trecho sem categoria própria (micropausa abaixo de 3 s, ou
# fala que o ASR não transcreveu) absorvido pela categoria em curso, que por
# regra NÃO é categoria 10.
_FALA, _SILENCIO, _ABSORVIDO = "speech", "silence", "carry"


@dataclass(frozen=True)
class CodedSegment:
    start_ms: int
    end_ms: int
    category: int


@dataclass(frozen=True)
class SpeechSpan:
    """Um trecho em que o diarizador detectou fala.

    Sem falante: a identidade de quem fala não entra em nenhuma regra que este
    motor implementa hoje. Quando a confusão for implementada ela vai precisar
    de sobreposição — e, portanto, de falante —, e é por isso que quem persiste
    a evidência deve guardar os turnos com rótulo, e não só a união deles."""
    start_ms: int
    end_ms: int


@dataclass(frozen=True)
class Mark:
    """Uma marca da folha de codificação: a categoria registrada e o trecho de
    aula que ela cobre.

    O trecho vem daqui, e não de `índice × 3 s`: com o relógio que reinicia a
    cada mudança, a enésima marca não começa mais em `n × 3 s`, e quem calcular
    o tempo pelo índice pinta além do fim da aula."""
    start_ms: int
    end_ms: int
    category: int


@dataclass(frozen=True)
class Coding:
    """A sequência de marcas, mais a contabilidade que o FIAS não enxerga.

    Para o FIAS — sequência, matriz e índices — a categoria 10 é uma só: é o que
    o método define, e `marks` não carrega de onde ela veio, de propósito, para
    que nenhum índice possa ser computado sobre a diferença. `silence_ms`
    sobrevive ao lado, como tempo bruto, para a rastreabilidade poder dizer
    "esta aula teve X s de silêncio" sem reprocessar. Não é índice, e não deve
    virar um.

    Não há `confusion_ms` porque não há detecção de confusão: um zero em toda
    aula se leria como "esta aula não teve confusão", que é uma afirmação que
    esta versão não pode fazer."""
    marks: list[Mark]
    silence_ms: int

    @property
    def intervals(self) -> list[int]:
        return [m.category for m in self.marks]


def _check(seg: CodedSegment) -> None:
    if seg.end_ms <= seg.start_ms or seg.start_ms < 0:
        raise ValueError(f"Segmento com tempo inválido: {seg}")
    if not 1 <= seg.category <= 10:
        raise ValueError(f"Categoria FIAS inválida: {seg.category}")


def _check_speech(span: SpeechSpan) -> None:
    if span.end_ms <= span.start_ms or span.start_ms < 0:
        raise ValueError(f"Trecho de fala com tempo inválido: {span}")


def _clip(spans: list[tuple[int, int]], total_ms: int) -> list[tuple[int, int]]:
    cortados = [(max(0, a), min(b, total_ms)) for a, b in spans]
    return [(a, b) for a, b in cortados if b > a]


def _union(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    unidos: list[list[int]] = []
    for a, b in sorted(spans):
        if unidos and a <= unidos[-1][1]:
            unidos[-1][1] = max(unidos[-1][1], b)
        else:
            unidos.append([a, b])
    return [(a, b) for a, b in unidos]


def _complement(spans: list[tuple[int, int]], total_ms: int) -> list[tuple[int, int]]:
    """O que sobra de [0, total_ms) fora de `spans` (já unidos e ordenados)."""
    fora, t = [], 0
    for a, b in spans:
        if a > t:
            fora.append((t, a))
        t = max(t, b)
    if t < total_ms:
        fora.append((t, total_ms))
    return _clip(fora, total_ms)


def _cobre(spans: list[tuple[int, int]], t: int) -> bool:
    return any(a <= t < b for a, b in spans)


def _resolver(segments: list[CodedSegment], silence: list[tuple[int, int]], total_ms: int,
              rules: dict, forced: list[CodedSegment]) -> list[list]:
    """A linha do tempo instante a instante, em camadas de prioridade:

    1. silêncio — o diarizador manda sobre o segmento do ASR, porque o segmento
       do ASR traz pausas coladas para dentro dele pelo VAD. Manda inclusive
       quando isso apaga um segmento inteiro: aí não é uma fala curta engolida
       por um vizinho maior (o defeito que esta mudança conserta), é uma
       discordância entre dois modelos — um mede voz, o outro produz texto — e
       ela se resolve a favor de quem mede voz.
    2. `forced` — segmento que NENHUMA marca representaria por estar escondido
       atrás de outro segmento. Aí sim vale a invariante "todo segmento
       codificado aparece ao menos uma vez": o que o esconde é a regra de
       codificação, não a evidência de fala.
    3. fala atribuível — a categoria que o classificador deu ao segmento.
    4. o resto — micropausa abaixo de 3 s, ou fala que o ASR não transcreveu:
       absorvida pela categoria em curso. Nunca 10: chamar de silêncio um trecho
       em que o diarizador ouviu voz trocaria dois opostos acústicos.
    """
    cat_silencio = rules["silence"]["category"]
    fronteiras = {0, total_ms}
    for s in segments:
        fronteiras |= {s.start_ms, s.end_ms}
    for a, b in silence:
        fronteiras |= {a, b}
    pontos = sorted(p for p in fronteiras if 0 <= p <= total_ms)

    trechos: list[list] = []
    for a, b in zip(pontos, pontos[1:]):
        if _cobre(silence, a):
            trechos.append([a, b, cat_silencio, _SILENCIO])
            continue
        # Desempate entre segmentos que cobrem o mesmo instante: quem começou
        # antes (aggregation.tie_break). O ASR não produz segmentos sobrepostos,
        # então na prática `forced` é só a rede de segurança.
        cobrindo = [s for s in forced if s.start_ms <= a < s.end_ms]
        if cobrindo:
            trechos.append([a, b, min(cobrindo, key=lambda s: s.start_ms).category, _FALA])
            continue
        cobrindo = [s for s in segments if s.start_ms <= a < s.end_ms]
        if cobrindo:
            trechos.append([a, b, min(cobrindo, key=lambda s: s.start_ms).category, _FALA])
            continue
        trechos.append([a, b, None, _ABSORVIDO])

    # O trecho absorvido herda a categoria em curso; antes da primeira categoria
    # da aula não há "em curso", então ele herda a que vem a seguir. Uma aula sem
    # categoria nenhuma (curta demais até para a regra 4) é silêncio: não há o
    # que absorva o trecho, e chamá-lo de outra coisa seria inventar.
    for i, trecho in enumerate(trechos):
        if trecho[2] is not None:
            continue
        anterior = next((t[2] for t in reversed(trechos[:i]) if t[2] is not None), None)
        seguinte = next((t[2] for t in trechos[i + 1:] if t[2] is not None), None)
        if anterior is None and seguinte is None:
            trecho[2], trecho[3] = cat_silencio, _SILENCIO
        else:
            trecho[2] = anterior if anterior is not None else seguinte
    return trechos


def _aparece(seg: CodedSegment, trechos: list[list], total_ms: int) -> bool:
    fim = min(seg.end_ms, total_ms)
    return any(c == seg.category and a < fim and seg.start_ms < b for a, b, c, _ in trechos)


def _merge(trechos: list[list]) -> list[tuple[int, int, int]]:
    """Funde trechos vizinhos de mesma categoria ANTES de marcar.

    Sem isto a contagem de marcas mede o picotamento do ASR, não a aula: uma
    fala contínua de 40 s que o ASR quebrou em seis segmentos viraria seis
    trechos de categoria 5, e a matriz ganharia cinco transições 5→5 que
    ninguém observou."""
    fundidos: list[list[int]] = []
    for a, b, c, _ in trechos:
        if fundidos and fundidos[-1][2] == c and fundidos[-1][1] == a:
            fundidos[-1][1] = b
        else:
            fundidos.append([a, b, c])
    return [(a, b, c) for a, b, c in fundidos]


def code_lesson(segments: list[CodedSegment], total_ms: int, rules: dict,
                speech: list[SpeechSpan] | None = None) -> Coding:
    """Codifica a aula inteira: as marcas, na ordem da linha do tempo.

    `speech` é a atividade de fala do diarizador. Sem ela (None) o motor só tem
    os próprios segmentos como evidência de fala — serve para os vetores de
    conformance e para quem não tem diarização, mas aí o silêncio é medido pelo
    VAD do ASR, que é a medida errada. Quem tem o diarizador passa o diarizador.
    """
    step = int(rules["coding"]["interval_seconds"] * 1000)
    protocolo = rules["interval_coding"]
    if (protocolo["policy"], protocolo["clock"]) != ("record_every_change", "restart_on_change"):
        raise ValueError(f"Protocolo de codificação não implementado: {protocolo}")
    for s in segments:
        _check(s)
    for f in speech or []:
        _check_speech(f)
    if total_ms <= 0:
        return Coding([], 0)

    ordenados = sorted(segments, key=lambda s: s.start_ms)
    fala = ([(f.start_ms, f.end_ms) for f in speech] if speech is not None
            else [(s.start_ms, s.end_ms) for s in ordenados])
    fala = _union(_clip(fala, total_ms))
    minimo = int(rules["silence"]["min_seconds"] * 1000)
    # Regra 4 com o limiar aplicado ao trecho de não-fala INTEIRO: pausa abaixo
    # de 3 s é micropausa respiratória, não silêncio pedagogicamente saliente.
    silencio = [(a, b) for a, b in _complement(fala, total_ms) if b - a >= minimo]

    trechos = _resolver(ordenados, silencio, total_ms, rules, forced=[])
    escondidos = [s for s in ordenados
                  if s.start_ms < total_ms and not _aparece(s, trechos, total_ms)]
    if escondidos:
        trechos = _resolver(ordenados, silencio, total_ms, rules, forced=escondidos)

    silence_ms = sum(b - a for a, b, _, origem in trechos if origem == _SILENCIO)
    unidos = (_merge(trechos) if protocolo["merge_adjacent_same_category"]
              else [(a, b, c) for a, b, c, _ in trechos])

    marcas: list[Mark] = []
    for a, b, c in unidos:
        t = a
        while t < b:
            marcas.append(Mark(t, min(t + step, b), c))
            t += step
    return Coding(marcas, silence_ms)


def segments_to_intervals(segments: list[CodedSegment], total_ms: int, rules: dict,
                          speech: list[SpeechSpan] | None = None) -> list[int]:
    """A sequência de categorias, sem os tempos. Quem precisa do tempo de cada
    marca (a faixa da tela) chama `code_lesson`."""
    return code_lesson(segments, total_ms, rules, speech).intervals


def transition_matrix(intervals: list[int], rules: dict) -> list[list[int]]:
    pad = rules["matrix"]["pad_category"]
    seq = [pad, *intervals, pad]
    m = [[0] * 10 for _ in range(10)]
    for a, b in zip(seq, seq[1:]):
        m[a - 1][b - 1] += 1
    return m
