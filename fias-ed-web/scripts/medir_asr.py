"""Mede tempo e pico de memória dos tamanhos de Whisper, em CPU (§21).

**Não mede WER, e isso é deliberado.** WER exigiria áudio real de aula com
transcrição de referência, que o projeto não tem. O áudio usado aqui é fala
sintetizada pelo libflite: serve para medir *custo de processamento* (o modelo
tem de ouvir fala de verdade, com envelope e formantes, senão o VAD do Whisper
descarta o arquivo inteiro e a medição vira o custo do VAD), e **não** serve
para medir acerto — o libflite lê com pronúncia inglesa. WER e DER seguem
`PENDING_SCIENTIFIC_VALIDATION`.

Mede com os mesmos parâmetros do produto (`app/ml/asr_whisper.py`): CPU,
`compute_type="int8"`, `language="pt"`, `temperature=0.0`, `vad_filter=True`.
Uma medição com outros parâmetros não diria nada sobre o tempo do produto.

Em produção o áudio é cortado em chunks de 10 min (`JANELA_PADRAO_MS` em
`app/audio/prepare.py`) e cada chunk vai ao ASR separadamente, em sequência.
Por isso medir até 10 min cobre o caso real inteiro: uma aula de 90 min é o
mesmo trabalho repetido 9 vezes, com o modelo carregado uma vez só.

**Não baixa modelo.** Quem baixa é `scripts/setup_models.py`, em revisão
fixada, no único momento em que há rede. Separar o que usa rede do que mede é
de propósito.

Pico de memória: `resource.getrusage(...).ru_maxrss`, da biblioteca padrão. É
marca d'água alta do processo e nunca desce, então cada célula da tabela roda
num processo próprio (este mesmo script, com `--uma-medicao`) — senão o pico
do `small` contaminaria a linha do `tiny`.

Uso:
    docker compose -f docker-compose.test.yml run --rm \
        -v fias-ed-web_models:/models:ro api-test python /app/scripts/medir_asr.py
"""
import argparse
import json
import math
import os
import resource
import subprocess  # nosec B404 - lista de argumentos, sem shell (§57)
import sys
import tempfile
import time
from pathlib import Path

# Vozes do próprio libflite (`ffmpeg -f lavfi -i flite=list_voices=1`), como em
# tests/audio_fixtures.py. Alternar voz e texto evita um sinal periódico, que o
# modelo poderia processar de um jeito atípico.
VOZES = ("slt", "rms", "awb", "kal16", "kal")
# Inventário grande de propósito: com poucas frases o áudio vira texto repetido,
# o Whisper entra em laço de repetição (ele condiciona a decodificação no texto
# anterior) e o custo por minuto dispara por um motivo que nenhuma aula real
# teria. Com 24 frases e 5 vozes, a primeira repetição de um mesmo par
# (frase, voz) só acontece depois de muitos minutos.
FRASES = (
    "hoje a gente vai falar sobre o problema da aula passada",
    "professor eu nao entendi a parte do meio dessa conta",
    "olha so para o quadro e me diz o que falta aqui",
    "quem quiser pode responder sem levantar a mao agora",
    "a resposta da letra be depende do que veio antes",
    "vamos tentar de novo com um numero menor para ver",
    "isso aqui cai na prova da semana que vem sim",
    "alguem lembra o nome daquele passo que a gente usou",
    "o resultado muda bastante se o sinal for trocado",
    "presta atencao no que acontece quando somo os dois lados",
    "essa linha do exercicio ficou meio confusa mesmo",
    "pode apagar o quadro que eu ja copiei tudo",
    "na pratica ninguem faz essa conta assim no papel",
    "eu tentei em casa e deu um valor bem diferente",
    "o livro usa outra letra mas o sentido e o mesmo",
    "vamos separar o grupo em quatro para comparar depois",
    "quem terminou pode ajudar a dupla do lado de la",
    "o erro mais comum e esquecer de inverter no final",
    "guardem essa ideia porque ela volta no proximo assunto",
    "hoje o tempo ficou curto entao paramos por aqui",
    "traz a folha do exercicio na aula de quinta feira",
    "a parte de baixo do quadro ninguem esta enxergando",
    "repete a pergunta mais alto para todo mundo ouvir",
    "faz sentido para voces ou repito de outro jeito",
)
JANELA_PRODUCAO_MIN = 10  # app/audio/prepare.py, JANELA_PADRAO_MS
AULA_LONGA_MIN = 90
# A extrapolação só sai se o custo por minuto se mantiver: razão entre o maior e
# o menor s/min de um mesmo tamanho abaixo disto. Acima, o tempo não é linear na
# duração e extrapolar seria inventar número.
TOLERANCIA_LINEARIDADE = 1.20


def _rodar(args: list[str]) -> str:
    return subprocess.run(  # nosec B603 B607 - lista de argumentos, sem shell
        args, check=True, capture_output=True, text=True).stdout


def _duracao_s(caminho: Path) -> float:
    return float(_rodar(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                         "-of", "csv=p=0", str(caminho)]).strip())


def gerar_fala(destino: Path, minutos: float) -> Path:
    """Fala sintetizada, repetida em ordem rotacionada até a duração alvo."""
    alvo = minutos * 60
    partes = []
    for i, texto in enumerate(FRASES):
        if any(c in texto for c in ":'\\"):
            raise ValueError("texto com caractere que o filtergraph do ffmpeg interpreta")
        parte = destino.with_name(f"{destino.stem}-f{i}.wav")
        _rodar(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                "-i", f"flite=text='{texto}':voice={VOZES[i % len(VOZES)]}",
                "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(parte)])
        partes.append(parte)
    duracoes = [_duracao_s(p) for p in partes]

    lista, linhas, total, i = destino.with_suffix(".txt"), [], 0.0, 0
    while total < alvo:
        # Passo primo com o número de frases: percorre o inventário inteiro
        # antes de repetir qualquer uma, e em ordem diferente da de geração.
        j = (i * 7 + 1) % len(partes)
        linhas.append(f"file '{partes[j].name}'")
        total += duracoes[j]
        i += 1
    lista.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    _rodar(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lista),
            "-t", f"{alvo:.3f}", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(destino)])
    for parte in partes:
        parte.unlink()
    lista.unlink()
    return destino


def uma_medicao(tamanho: str, caminho: Path) -> dict:
    """Roda no processo filho: carrega o modelo, transcreve e reporta o pico de RSS."""
    from faster_whisper import WhisperModel

    diretorio = Path(os.environ.get("MODELS_DIR", "/models")) / f"faster-whisper-{tamanho}"
    if not (diretorio / "model.bin").is_file():
        raise SystemExit(f"peso ausente em {diretorio}: baixe antes com scripts/setup_models.py"
                         f" (FIAS_ED_ASR_SIZE={tamanho}); este script não baixa modelo.")
    t0 = time.monotonic()
    modelo = WhisperModel(str(diretorio), device="cpu", compute_type="int8", local_files_only=True)
    carga_s = time.monotonic() - t0

    t0 = time.monotonic()
    segmentos, _ = modelo.transcribe(str(caminho), language="pt", temperature=0.0, vad_filter=True)
    # O gerador só faz trabalho quando consumido. Conta-se a quantidade, nunca o
    # texto: log com transcrição é proibido (§57).
    n = sum(1 for _ in segmentos)
    return {"tamanho": tamanho, "carga_s": carga_s, "transcricao_s": time.monotonic() - t0,
            "segmentos": n,
            "pico_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}


def _celula(tamanho: str, caminho: Path) -> dict:
    proc = subprocess.run(  # nosec B603 - lista de argumentos, sem shell
        [sys.executable, str(Path(__file__).resolve()), "--uma-medicao", tamanho, str(caminho)],
        capture_output=True, text=True)
    if proc.returncode:
        # Sem isto a mensagem do filho (peso ausente, por exemplo) some dentro
        # do capture_output e o erro vira um rastro de CalledProcessError.
        raise SystemExit(f"a medição de {tamanho} falhou:\n{proc.stderr.strip()}")
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _tabela(medicoes: list[dict]) -> list[str]:
    linhas = ["| Modelo | Duração do áudio | Carga do modelo | Transcrição | s por min de áudio"
              " | Pico de memória | Segmentos |", "|---|---|---|---|---|---|---|"]
    for m in medicoes:
        linhas.append(
            f"| {m['tamanho']} | {m['minutos']:g} min | {m['carga_s']:.1f} s |"
            f" {m['transcricao_s']:.1f} s | {m['transcricao_s'] / m['minutos']:.1f} |"
            f" {m['pico_bytes'] / 1e9:.2f} GB | {m['segmentos']} |")
    return linhas


def _linearidade(medicoes: list[dict], tamanho: str) -> tuple[float, list[float]]:
    razoes = [m["transcricao_s"] / m["minutos"] for m in medicoes if m["tamanho"] == tamanho]
    return (max(razoes) / min(razoes) if len(razoes) > 1 else float("inf")), razoes


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Tempo e pico de memória do ASR (§21).")
    p.add_argument("--tamanhos", nargs="+", default=["tiny", "base", "small"])
    p.add_argument("--minutos", nargs="+", type=float, default=[2.5, 5.0, 10.0])
    p.add_argument("--uma-medicao", nargs=2, metavar=("TAMANHO", "WAV"),
                   help="uso interno: mede uma célula e imprime JSON")
    args = p.parse_args(argv)

    if args.uma_medicao:
        print(json.dumps(uma_medicao(args.uma_medicao[0], Path(args.uma_medicao[1]))))
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        audios = {}
        for minutos in sorted(args.minutos):
            print(f"gerando {minutos:g} min de fala…", file=sys.stderr, flush=True)
            audios[minutos] = gerar_fala(Path(tmp) / f"fala-{minutos:g}.wav", minutos)
        medicoes = []
        for tamanho in args.tamanhos:
            for minutos in sorted(args.minutos):
                print(f"medindo {tamanho} em {minutos:g} min…", file=sys.stderr, flush=True)
                m = _celula(tamanho, audios[minutos]) | {"minutos": minutos}
                if not m["segmentos"]:
                    raise SystemExit(f"{tamanho} em {minutos:g} min devolveu zero segmento:"
                                     " sem transcrição não há o que medir.")
                medicoes.append(m)

    print("\n".join(["### Medido", ""] + _tabela(medicoes)))
    print("\n### Linearidade do tempo na duração do áudio\n")
    print("| Modelo | s por min (menor → maior duração) | Maior / menor |")
    print("|---|---|---|")
    for tamanho in args.tamanhos:
        razao, valores = _linearidade(medicoes, tamanho)
        print(f"| {tamanho} | {' → '.join(f'{v:.1f}' for v in valores)} | {razao:.2f} |")

    print(f"\n### Extrapolado para uma aula de {AULA_LONGA_MIN} min\n")
    chunks = math.ceil(AULA_LONGA_MIN / JANELA_PRODUCAO_MIN)
    for tamanho in args.tamanhos:
        razao, _ = _linearidade(medicoes, tamanho)
        do_tamanho = [m for m in medicoes if m["tamanho"] == tamanho]
        janela = [m for m in do_tamanho if m["minutos"] == JANELA_PRODUCAO_MIN]
        maior = max(do_tamanho, key=lambda m: m["minutos"])
        pico = max(m["pico_bytes"] for m in do_tamanho)
        espalhamento = pico / min(m["pico_bytes"] for m in do_tamanho)
        if janela:
            # Não depende da linearidade: em produção a unidade repetida é
            # exatamente este chunk, medido, e cada chamada ao ASR começa do
            # zero. A extrapolação é só a contagem de repetições.
            total = janela[0]["carga_s"] + chunks * janela[0]["transcricao_s"]
            base = (f"{chunks} x o chunk de {JANELA_PRODUCAO_MIN} min medido, mais uma carga"
                    " de modelo — que é como o produto roda")
        elif razao <= TOLERANCIA_LINEARIDADE:
            total = maior["carga_s"] + AULA_LONGA_MIN * maior["transcricao_s"] / maior["minutos"]
            base = (f"custo por minuto do ponto de {maior['minutos']:g} min, que se manteve"
                    f" ({razao:.2f}x entre as durações medidas)")
        else:
            print(f"- **{tamanho}: não extrapolado.** O custo por minuto variou {razao:.2f}x entre"
                  " as durações medidas, e não há ponto medido na janela de"
                  f" {JANELA_PRODUCAO_MIN} min que o produto usa. Extrapolar daqui seria inventar"
                  " número.")
            continue
        print(f"- **{tamanho}: ~{total / 60:.0f} min de processamento**"
              f" ({total / (AULA_LONGA_MIN * 60):.2f}x a duração do áudio) — {base}."
              f" Pico de memória: {pico / 1e9:.2f} GB, medido, não extrapolado"
              f" (variou {espalhamento:.2f}x entre as durações, contra"
              f" {max(args.minutos) / min(args.minutos):.0f}x de áudio).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
