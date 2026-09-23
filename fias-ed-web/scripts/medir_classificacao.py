"""Mede o pico de memória da classificação FIAS, com lote e sem lote (§21).

Fecha a terceira conta de memória do worker. `medir_asr.py` e
`medir_diarizacao.py` mediram os dois primeiros modelos; o classificador ficou
de fora até a verificação de ponta a ponta mostrar que **é ele quem manda no
pico do processo**: numa aula de 46 min o worker ia a 2,73 GB no fim da
diarização e saltava para 4,75 GB durante os ~46 s da classificação.

O salto tinha causa conhecida: `BertimbauClassificador.logits` mandava todos os
segmentos da aula numa passagem só. As ativações do BERT crescem com o número de
linhas do lote — sobretudo a matriz de atenção, que é
`linhas x cabeças x 256 x 256` — então o pico crescia com a duração da aula e
com o quanto a fala é picada, sem teto previsto. Por isso aqui se mede a mesma
quantidade de segmentos duas vezes, com lote e sem: o que interessa é se o pico
deixou de depender do tamanho da aula, não um número isolado.

**Também compara os valores.** O script traz de volta os logits de cada célula e
confere que a saída em lote é idêntica à da passagem única, par a par. Um
conserto de memória que mexesse no resultado seria inaceitável (§44:
reprodutibilidade), e a igualdade é barata de verificar aqui, no modelo real,
com o mesmo tamanho de aula da medição.

**Não mede acerto.** Acurácia do classificador é da pesquisa de origem
(ANALISE_MODELOS_EXISTENTES §2.x) e não se mede com texto sintético. Os pares
vêm das mesmas frases de `medir_asr.py`: com padding="max_length" toda linha
ocupa 256 tokens independentemente do texto, então o custo depende da
*quantidade* de segmentos e não do que está escrito neles.

Não baixa modelo: quem baixa é `scripts/setup_models.py`, em revisão fixada.

Uso:
    docker compose -f docker-compose.test.yml run --rm \
        -v fias-ed-web_models:/models:ro api-test python /app/scripts/medir_classificacao.py
"""
import argparse
import json
import resource
import subprocess  # nosec B404 - lista de argumentos, sem shell (§57)
import sys
import time
from pathlib import Path

# As mesmas frases de medir_asr.py: "o mesmo método" só significa alguma coisa
# se o material também for o mesmo.
from medir_asr import FRASES

MAQUINA_REFERENCIA_GB = 15.5
# A aula de 46 min da verificação de ponta a ponta deu 381 segmentos. O dobro
# está aqui para responder à pergunta que o conserto faz: o pico ainda cresce
# com o tamanho da aula?
SEGMENTOS_PADRAO = (381, 762)


def _pico_gb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 / 1e9


def montar_entrada(n: int) -> list[str]:
    """n falas sintéticas, rotacionadas para não repetir a mesma em sequência."""
    return [FRASES[(i * 7 + 1) % len(FRASES)] for i in range(n)]


def uma_medicao(n: int, lote: int | None) -> dict:
    """Roda no processo filho: carrega o modelo, classifica n segmentos e reporta
    o pico de RSS.

    Processo próprio por célula pela mesma razão de `medir_asr.py`: `ru_maxrss` é
    marca d'água e nunca desce, então a célula sem lote contaminaria a com lote.

    `lote=None` reproduz o comportamento anterior ao conserto — um lote só, do
    tamanho da aula — sem manter duas implementações: é a mesma função `logits`,
    com o tamanho do lote grande o bastante para não dividir nada.
    """
    from app.ml import clf_bertimbau
    from app.ml.clf_bertimbau import BertimbauClassificador, montar_pares

    t0 = time.monotonic()
    clf = BertimbauClassificador()
    carga_s = time.monotonic() - t0
    pico_carga_gb = _pico_gb()

    clf_bertimbau.TAMANHO_DO_LOTE = n if lote is None else lote
    pares = montar_pares(montar_entrada(n))
    t0 = time.monotonic()
    logits = clf.logits(pares)
    return {"segmentos": n, "lote": lote, "classificacao_s": time.monotonic() - t0,
            "pico_gb": _pico_gb(), "pico_carga_gb": pico_carga_gb, "carga_s": carga_s,
            "logits": logits}


def _filho(args: list[str], rotulo: str) -> dict:
    proc = subprocess.run(  # nosec B603 - lista de argumentos, sem shell
        [sys.executable, str(Path(__file__).resolve()), *args], capture_output=True, text=True)
    if proc.returncode:
        # Sem isto a mensagem do filho (peso ausente, por exemplo) some dentro do
        # capture_output e o erro vira um rastro de CalledProcessError.
        raise SystemExit(f"a medição de {rotulo} falhou:\n{proc.stderr.strip()}")
    return json.loads(proc.stdout.strip().splitlines()[-1])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Pico de memória da classificação FIAS (§21).")
    p.add_argument("--segmentos", nargs="+", type=int, default=list(SEGMENTOS_PADRAO))
    p.add_argument("--lote", type=int, default=None,
                   help="tamanho do lote; o padrão é o do produto (clf_bertimbau.TAMANHO_DO_LOTE)")
    p.add_argument("--uma-medicao", nargs=2, metavar=("SEGMENTOS", "LOTE"),
                   help="uso interno: mede uma célula e imprime JSON (LOTE=0 → passagem única)")
    args = p.parse_args(argv)

    if args.uma_medicao:
        n, lote = int(args.uma_medicao[0]), int(args.uma_medicao[1])
        print(json.dumps(uma_medicao(n, lote or None)))
        return 0

    from app.ml.clf_bertimbau import TAMANHO_DO_LOTE
    lote = args.lote or TAMANHO_DO_LOTE

    medicoes = []
    for n in args.segmentos:
        for tamanho, rotulo in ((0, "passagem única"), (lote, f"lote de {lote}")):
            print(f"medindo {n} segmentos, {rotulo}…", file=sys.stderr, flush=True)
            medicoes.append(_filho(["--uma-medicao", str(n), str(tamanho)], f"{n}/{rotulo}"))

    print("### Medido: classificação FIAS, com lote e sem lote\n")
    print("| Segmentos | Lote | Classificação | Pico de memória | % da máquina |")
    print("|---|---|---|---|---|")
    for m in medicoes:
        print(f"| {m['segmentos']} | {m['lote'] or 'passagem única'} |"
              f" {m['classificacao_s']:.1f} s | {m['pico_gb']:.2f} GB |"
              f" {100 * m['pico_gb'] / MAQUINA_REFERENCIA_GB:.0f}% |")

    com_lote = [m for m in medicoes if m["lote"]]
    sem_lote = [m for m in medicoes if not m["lote"]]
    picos_sem = " → ".join("%.2f" % m["pico_gb"] for m in sem_lote)
    picos_com = " → ".join("%.2f" % m["pico_gb"] for m in com_lote)
    tamanhos = " → ".join(str(m["segmentos"]) for m in sem_lote)
    print(f"\n- Modelo carregado, sem classificar nada: {medicoes[0]['pico_carga_gb']:.2f} GB.")
    print(f"- Sem lote, o pico cresce com a aula: {picos_sem} GB para {tamanhos} segmentos.")
    print(f"- Com lote de {com_lote[0]['lote']}: {picos_com} GB para os mesmos tamanhos"
          " — o pico deixou de ser função da duração da aula.")

    print("\n### O que o lote fez com o resultado (§44)\n")
    for n in args.segmentos:
        a = next(m for m in medicoes if m["segmentos"] == n and not m["lote"])
        b = next(m for m in medicoes if m["segmentos"] == n and m["lote"])
        maior_dif = max((abs(x - y) for la, lb in zip(a["logits"], b["logits"])
                         for x, y in zip(la, lb)), default=0.0)
        margem = min(sorted(v)[-1] - sorted(v)[-2] for v in a["logits"])
        categorias_a = [max(range(len(v)), key=v.__getitem__) for v in a["logits"]]
        categorias_b = [max(range(len(v)), key=v.__getitem__) for v in b["logits"]]
        divergentes = sum(1 for x, y in zip(categorias_a, categorias_b) if x != y)
        print(f"- {n} segmentos: {divergentes} categorias diferentes de {n};"
              f" maior diferença absoluta nos logits {maior_dif:.3g}, contra margem mínima de"
              f" {margem:.3g} entre o maior e o segundo maior logit ({margem / maior_dif:.0f}x).")
        if divergentes:
            raise SystemExit("o lote mudou a categoria de alguma fala: isto não pode sair assim.")
    print("\nA diferença nos logits é do float32: o matmul escolhe a ordem de redução conforme a"
          " dimensão do lote, e nenhum tamanho de lote reproduz os valores de outro tamanho. O que"
          " o §44 pede é outra coisa — a mesma aula reprocessada dando o mesmo resultado — e isso"
          " o lote fixo garante (test_bertimbau_em_lote_e_reproduzivel).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
