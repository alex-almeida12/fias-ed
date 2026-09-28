"""Mede tempo e pico de memória da diarização, em CPU (§21).

Fecha a conta que "Escolha do modelo de ASR" no README deixou aberta: o pico do
ASR (1,14 GB) foi medido, mas o do `pyannote` estava marcado como desconhecido
porque os repositórios dele eram *gated* e os pesos não estavam nesta máquina.
Agora estão.

**Não mede DER, e isso é deliberado**, pelo mesmo motivo que `medir_asr.py` não
mede WER: DER exigiria áudio real de aula com diarização de referência, que o
projeto não tem. O áudio é fala sintetizada pelo libflite (cinco vozes), o
mesmo gerador de `medir_asr.py` — serve para medir *custo de processamento*, e
não para medir acerto. DER segue `PENDING_SCIENTIFIC_VALIDATION`.

**A diferença que muda tudo em relação ao ASR:** o ASR vê o áudio em pedaços de
10 min (`JANELA_PADRAO_MS` em `app/audio/prepare.py`), então o pico de memória
dele é o do maior pedaço e não cresce com a aula. A diarização **não é
cortada** — `handle_diarize` entrega o arquivo de trabalho inteiro ao pipeline
(`app/jobs/handlers.py`). Numa aula de 90 min, o pyannote recebe 90 min de uma
vez. Por isso aqui se mede em várias durações: o que interessa é como o pico
cresce, não um número isolado.

O modo `--combinado` mede num processo só o que o worker faz numa aula: ASR
primeiro, diarização depois. É esse número que responde se os dois cabem na
máquina — somar dois picos medidos em processos separados daria um limite
superior grosseiro, e tomar o maior dos dois daria um otimista. O worker é um
processo só (`app/jobs/worker.py`) e `ru_maxrss` é a marca d'água dele.

Não baixa modelo: quem baixa é `scripts/setup_models.py`, em revisão fixada.

Uso:
    docker compose -f docker-compose.test.yml run --rm \
        -v fias-ed-web_models:/models:ro api-test python /app/scripts/medir_diarizacao.py
"""
import argparse
import json
import resource
import subprocess  # nosec B404 - lista de argumentos, sem shell (§57)
import sys
import tempfile
import time
from pathlib import Path

# O gerador de fala é o de medir_asr.py de propósito: "o mesmo método" só
# significa alguma coisa se o áudio também for o mesmo. As cinco vozes do
# libflite dão à diarização o que separar; um arquivo de voz única mediria o
# custo de um caso que nenhuma aula tem.
from medir_asr import AULA_LONGA_MIN, gerar_fala

MAQUINA_REFERENCIA_GB = 15.5


def _pico_gb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 / 1e9


def uma_medicao(caminho: Path) -> dict:
    """Roda no processo filho: carrega o pipeline, diariza e reporta o pico de RSS.

    Processo próprio por célula pela mesma razão de `medir_asr.py`: `ru_maxrss`
    é marca d'água e nunca desce, então a célula de 30 min contaminaria a de
    2,5 min se dividissem processo.
    """
    from app.ml.diar_pyannote import PyannoteDiarizador

    t0 = time.monotonic()
    diarizador = PyannoteDiarizador()
    carga_s = time.monotonic() - t0
    pico_carga = _pico_gb()

    t0 = time.monotonic()
    turnos = diarizador.turnos(caminho)
    # Contagem e rótulos, nunca texto: log com transcrição é proibido (§57).
    return {"carga_s": carga_s, "diarizacao_s": time.monotonic() - t0,
            "turnos": len(turnos), "vozes": len({t.rotulo for t in turnos}),
            "pico_carga_gb": pico_carga, "pico_gb": _pico_gb()}


def combinado(caminho: Path, tamanho: str) -> dict:
    """ASR e depois diarização, no mesmo processo — a forma do worker.

    O worker roda os dois estágios em sequência, no mesmo processo Python
    (`app/jobs/worker.py`). O objeto do Whisper morre no fim do handler, mas o
    alocador do C não devolve tudo ao sistema: o pico do processo depois dos
    dois não é nem a soma nem o máximo dos dois isolados, é o que se mede aqui.

    O ASR recebe o áudio inteiro, e não em chunks de 10 min como em produção.
    É o caso mais caro: em produção cada chunk é uma chamada que começa do zero.
    """
    import os

    from faster_whisper import WhisperModel

    diretorio = Path(os.environ.get("MODELS_DIR", "/models")) / f"faster-whisper-{tamanho}"
    t0 = time.monotonic()
    modelo = WhisperModel(str(diretorio), device="cpu", compute_type="int8", local_files_only=True)
    segmentos, _ = modelo.transcribe(str(caminho), language="pt", temperature=0.0, vad_filter=True)
    n = sum(1 for _ in segmentos)
    asr_s, pico_asr = time.monotonic() - t0, _pico_gb()
    del modelo, segmentos

    from app.ml.diar_pyannote import PyannoteDiarizador

    t0 = time.monotonic()
    turnos = PyannoteDiarizador().turnos(caminho)
    return {"asr_s": asr_s, "segmentos": n, "pico_apos_asr_gb": pico_asr,
            "diarizacao_s": time.monotonic() - t0, "turnos": len(turnos),
            "pico_gb": _pico_gb()}


def _filho(argumentos: list[str], rotulo: str) -> dict:
    proc = subprocess.run(  # nosec B603 - lista de argumentos, sem shell
        [sys.executable, str(Path(__file__).resolve()), *argumentos],
        capture_output=True, text=True)
    if proc.returncode:
        raise SystemExit(f"a medição de {rotulo} falhou:\n{proc.stderr.strip()}")
    return json.loads(proc.stdout.strip().splitlines()[-1])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Tempo e pico de memória da diarização (§21).")
    p.add_argument("--minutos", nargs="+", type=float, default=[2.5, 5.0, 10.0, 30.0])
    p.add_argument("--asr-size", default="small")
    p.add_argument("--combinado-min", type=float, default=10.0,
                   help="duração da medição ASR+diarização no mesmo processo")
    p.add_argument("--uma-medicao", metavar="WAV", help="uso interno: mede uma célula")
    p.add_argument("--um-combinado", nargs=2, metavar=("WAV", "TAMANHO"), help="uso interno")
    args = p.parse_args(argv)

    if args.uma_medicao:
        print(json.dumps(uma_medicao(Path(args.uma_medicao))))
        return 0
    if args.um_combinado:
        print(json.dumps(combinado(Path(args.um_combinado[0]), args.um_combinado[1])))
        return 0

    duracoes = sorted(set(args.minutos) | {args.combinado_min})
    with tempfile.TemporaryDirectory() as tmp:
        audios = {}
        for minutos in duracoes:
            print(f"gerando {minutos:g} min de fala…", file=sys.stderr, flush=True)
            audios[minutos] = gerar_fala(Path(tmp) / f"fala-{minutos:g}.wav", minutos)
        medicoes = []
        for minutos in sorted(args.minutos):
            print(f"diarizando {minutos:g} min…", file=sys.stderr, flush=True)
            m = _filho(["--uma-medicao", str(audios[minutos])], f"{minutos:g} min")
            m |= {"minutos": minutos}
            if not m["turnos"]:
                raise SystemExit(
                    f"{minutos:g} min devolveu zero turno: sem diarização não há o que medir.")
            medicoes.append(m)
        print(f"medindo ASR+diarização juntos em {args.combinado_min:g} min…",
              file=sys.stderr, flush=True)
        junto = _filho(["--um-combinado", str(audios[args.combinado_min]), args.asr_size],
                       "combinado")

    print("### Medido: diarização sozinha\n")
    print("| Duração do áudio | Carga do pipeline | Diarização | s por min de áudio"
          " | Pico de memória | Turnos | Vozes |")
    print("|---|---|---|---|---|---|---|")
    for m in medicoes:
        print(f"| {m['minutos']:g} min | {m['carga_s']:.1f} s | {m['diarizacao_s']:.1f} s |"
              f" {m['diarizacao_s'] / m['minutos']:.1f} | {m['pico_gb']:.2f} GB |"
              f" {m['turnos']} | {m['vozes']} |")

    por_min = [m["diarizacao_s"] / m["minutos"] for m in medicoes]
    picos = [m["pico_gb"] for m in medicoes]
    menor, maior = medicoes[0], medicoes[-1]
    print(f"\n- Custo por minuto: {' → '.join(f'{v:.1f}' for v in por_min)} s/min"
          f" ({max(por_min) / min(por_min):.2f}x entre a menor e a maior duração).")
    print(f"- Pico de memória: {' → '.join(f'{v:.2f}' for v in picos)} GB"
          f" ({max(picos) / min(picos):.2f}x, para"
          f" {maior['minutos'] / menor['minutos']:.0f}x de áudio).")
    print(f"- Carga do pipeline, sem áudio nenhum: {medicoes[0]['pico_carga_gb']:.2f} GB.")

    print(f"\n### Medido: ASR ({args.asr_size}) e diarização no mesmo processo,"
          f" {args.combinado_min:g} min\n")
    print(f"- ASR: {junto['asr_s']:.1f} s, {junto['segmentos']} segmentos;"
          f" pico do processo ao fim do ASR: {junto['pico_apos_asr_gb']:.2f} GB.")
    print(f"- Diarização em seguida: {junto['diarizacao_s']:.1f} s, {junto['turnos']} turnos.")
    print(f"- **Pico do processo com os dois estágios: {junto['pico_gb']:.2f} GB**"
          f" — {100 * junto['pico_gb'] / MAQUINA_REFERENCIA_GB:.0f}% dos"
          f" {MAQUINA_REFERENCIA_GB:g} GB da máquina de referência.")

    print(f"\n### O que falta para fechar a aula de {AULA_LONGA_MIN} min\n")
    print("A diarização não é cortada em chunks: `handle_diarize` entrega o áudio inteiro ao"
          f" pipeline. A maior duração medida aqui é {maior['minutos']:g} min, e o pico cresceu"
          f" {max(picos) / min(picos):.2f}x de {menor['minutos']:g} para"
          f" {maior['minutos']:g} min. Um número para 90 min só vale medido — a tabela acima"
          " diz como cresce, não quanto dá.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
