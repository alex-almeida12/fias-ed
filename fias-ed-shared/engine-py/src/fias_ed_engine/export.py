"""Exportação do dataset de uma ou mais aulas (JSON e ZIP de CSVs). Sem áudio, sem texto por padrão.

Cada item de `lessons` traz `lesson`, `segments`, `qti_responses`, `processing`
e, opcionalmente, `speech`: a linha do tempo de fala do diarizador
(`list[SpeechSpan]`), a mesma evidência que a tela do professor usa para medir
silêncio. Sem ela o motor cai nos próprios segmentos do ASR e mede outra coisa —
o dataset diria SC ≈ 0,0038 para a aula em que a tela mostra 0,0725 —, então
cada aula declara, em `silence_source`, qual das duas fontes foi usada. A
declaração sai na coluna `silence_source` da tabela `lessons` (é ali que o
analista olha: quem abre só `lessons.csv` não tem o manifesto por perto) e
também em `manifest.processing`, junto dos modelos; as duas saem do mesmo valor,
calculado uma vez por aula.

`processing.rules_version` é obrigatório: é por ele que a exportação recusa
juntar aulas de versões de regra diferentes (ver `_versao_unica`)."""
import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path

from .indices import compute_indices
from .intervals import CodedSegment, code_lesson, transition_matrix
from .mtss import build_facts, evaluate, recommendations
from .qti import aggregate
from .rules import load_rules
from .triangulation import triangulate

# 2.0.0 porque o conteúdo de `intervals` e `indices` mudou de significado com
# rules_version 2.0.0, e não só de valor: uma linha de `intervals` deixou de ser
# um balde fixo de 3 s (`start_ms` = índice × 3 s) e passou a ser a marca que o
# protocolo registra, com o tempo que ela cobre de fato; `n_intervals` deixou de
# ser duração / 3 s; e a categoria 10 passou a existir, com o silêncio medido
# pela evidência de fala do diarizador. Quem empilhar um dataset 1.0.0 com um
# desta versão soma grandezas diferentes — o mesmo defeito que `_versao_unica`
# recusa dentro de um dataset, um nível acima. O número da versão é o único
# aviso que chega a quem abrir os arquivos meses depois.
#
# 2.1.0 (e não 2.0.1 nem 2.0.0): `lessons` ganhou a coluna `silence_source`, que
# o schema exige. Nenhum valor das colunas antigas mudou, por isso não é 3.0.0 —
# mas um dataset 2.0.0 não tem a coluna e falha a validação de hoje, e é pelo
# número da versão que se distingue "exportado antes" de "exportado errado".
EXPORT_VERSION = "2.1.0"
TABLES = ("lessons", "segments", "intervals", "matrix", "indices", "qti_responses",
          "qti_results", "mtss", "recommendations", "triangulation")
_LESSON_FIELDS = ("lesson_id", "lesson_date", "disciplina", "turma_id", "duration_ms", "transcript_source")
_SEGMENT_FIELDS = ("segment_id", "start_ms", "end_ms", "role", "pred_raw", "pred_role_constrained", "confidence", "uncertain")
_PROCESSING_FIELDS = ("app_version", "fias_model", "fias_model_hash", "asr_model", "asr_model_hash",
                      "diarization_model", "rules_version")

# Como o silêncio (categoria 10) foi medido em cada aula. Um dataset em que
# metade das aulas mede silêncio pela detecção de fala e metade pela extensão
# dos segmentos do ASR, sem dizer qual é qual, não permite ao analista separar
# as duas — e as duas medidas diferem por uma ordem de grandeza (na aula medida
# em 2026-09-23: 78 249 ms contra 4 000 ms).
#
# O nome é `silence_source`, e não `speech_source`, por causa do vizinho:
# `transcript_source` já diz de onde veio o TEXTO (ASR ou revisão do professor).
# Duas colunas chamadas "…_source" com "transcript" e "speech" ao lado leem-se
# como sinônimos; nomeando pela grandeza que a escolha afeta — o silêncio —, a
# linha "transcript_source=TRANSCRICAO_REVISADA, silence_source=asr_segments"
# se explica sozinha, que é o teste de um cabeçalho de planilha.
_SILENCE_FROM_DIARIZATION = "diarization_speech_activity"
_SILENCE_FROM_SEGMENTS = "asr_segments"

# Colunas fixas por tabela do CSV, na ordem em que o cabeçalho é escrito —
# sempre as mesmas colunas, com ou sem linhas, para que Web e Android
# exportem arquivos byte-idênticos dado o mesmo dataset (ver DATABASE_MODEL.md).
TABLE_FIELDS: dict[str, tuple[str, ...]] = {
    "lessons": ("lesson_id", *_LESSON_FIELDS[1:], "silence_source", "n_segments", "n_intervals", "rules_version"),
    "segments": ("lesson_id", *_SEGMENT_FIELDS, "text_pseudonymized"),
    "intervals": ("lesson_id", "interval_index", "start_ms", "category"),
    "matrix": ("lesson_id", "from_category", "to_category", "count"),
    "indices": ("lesson_id", "index_id", "value", "reason", "numerator_count", "denominator_count", "validation_status"),
    "qti_responses": ("lesson_id", "response_index", *(f"q{i}" for i in range(1, 25))),
    "qti_results": ("lesson_id", "response_count", "displayable", *(f"oc{i}" for i in range(1, 9)), "agency", "communion"),
    "mtss": ("lesson_id", "rule_id", "tier1_dimension", "framing", "validation_status", "rules_version"),
    "recommendations": ("lesson_id", "recommendation_id", "rule_id", "validation_status"),
    "triangulation": ("lesson_id", "pair_id", "fias_value", "qti_available", "qti_values"),
}


class ExportPrivacyError(ValueError):
    pass


class ExportRulesVersionError(ValueError):
    pass


def _versao_unica(lessons: list[dict], motor: str) -> None:
    """Recusa o dataset que misturaria versões de regra.

    `build_dataset` é o único ponto do sistema em que aulas diferentes entram na
    mesma tabela, então é aqui que a mistura tem de parar. Entre 1.0.0 e 2.0.0 a
    mudança não é de valor: `n_intervals` deixou de ser duração / 3 s, a
    sequência passou a registrar cada mudança de categoria e a categoria 10
    passou a existir. Uma média entre um SC de 1.0.0 e um de 2.0.0 não mede
    coisa nenhuma. Entre 2.0.0 e 3.0.0 as tabelas têm as mesmas colunas, e por
    isso a mistura é ainda mais silenciosa: o que mudou foi a categoria gravada
    em cada segmento, porque o contexto passou a chegar ao classificador só
    quando há troca de falante.

    Recusa, e não aviso: o aviso mora no manifesto de um arquivo que vai ser
    aberto meses depois, provavelmente por outra pessoa, e o dano da mistura é
    silencioso — a tabela sai bonita e a média sai errada. Recusar custa uma
    exportação repetida; não recusar custa um resultado de dissertação.

    A versão declarada tem de ser a do motor que vai codificar, e não só igual
    entre as aulas: `build_dataset` recodifica tudo com as regras carregadas
    agora, de modo que exportar uma aula de 1.0.0 produziria tabelas da versão
    do motor com carimbo 1.0.0. Não há conversão entre as versões, e inventar
    uma seria o mesmo defeito com outra roupa."""
    por_versao: dict[str, list[str]] = {}
    for item in lessons:
        declarada = item["processing"].get("rules_version") or "(não declarada)"
        por_versao.setdefault(declarada, []).append(str(item["lesson"]["lesson_id"]))
    if set(por_versao) == {motor}:
        return
    detalhe = "; ".join(f"{v}: {', '.join(sorted(ids))}" for v, ids in sorted(por_versao.items()))
    raise ExportRulesVersionError(
        f"Exportação recusada: as aulas selecionadas não estão todas na versão de regras do motor "
        f"({motor}). Indicadores de versões diferentes não são a mesma grandeza — de 1.0.0 para "
        f"2.0.0, n_intervals deixou de ser duração / 3 s, a sequência passou a registrar cada "
        f"mudança de categoria e a categoria 10 passou a existir; de 2.0.0 para 3.0.0, o turno "
        f"anterior passou a ser enviado ao classificador como contexto apenas quando há troca de "
        f"falante, e com isso mudou a categoria da maioria dos segmentos e os índices calculados "
        f"a partir delas —, e não existe conversão entre elas. Aulas por versão declarada: "
        f"{detalhe}.")


def build_dataset(lessons: list[dict], include_text: bool, exported_at: str) -> dict:
    if not lessons:
        raise ValueError("Nenhuma aula selecionada para exportação.")
    F, Q, M, P = (load_rules(n) for n in ("fias_rules", "qti_config", "mtss_rules", "pedagogical_rules"))
    _versao_unica(lessons, F["rules_version"])
    ds: dict = {t: [] for t in TABLES}
    processing = []
    for item in lessons:
        meta, segs = item["lesson"], item["segments"]
        lid = meta["lesson_id"]
        if include_text and any(not s.get("text_pseudonymized") for s in segs):
            raise ExportPrivacyError(f"Aula {lid}: há falas sem versão pseudonimizada; exportação com texto recusada.")
        coded = [CodedSegment(s["start_ms"], s["end_ms"], s["pred_role_constrained"]) for s in segs]
        # `speech` é a linha do tempo de fala do diarizador (list[SpeechSpan]),
        # a mesma que a tela do professor usa. Ausente (ou None) significa "não
        # se sabe", e o motor cai nos próprios segmentos: é a medida pior, mas
        # nunca inventa silêncio. Aula processada antes da versão que passou a
        # gravar a evidência cai nesse caso, e a linha dela em `lessons` diz que caiu.
        fala = item.get("speech")
        # Calculado UMA vez por aula e escrito nos dois lugares a partir desta
        # variável. Dois cálculos separados do mesmo fato foi o defeito que esta
        # fatia já consertou duas vezes (a revisão fixada dos modelos, o pino em
        # dois lugares): aqui a coluna e o manifesto não têm como discordar.
        fonte_silencio = _SILENCE_FROM_SEGMENTS if fala is None else _SILENCE_FROM_DIARIZATION
        coding = code_lesson(coded, meta["duration_ms"], F, fala)
        intervals = coding.intervals
        indices = compute_indices(intervals, F, n_segments=len(segs), confidences=[s["confidence"] for s in segs])
        answers = [{int(k): v for k, v in r.items()} for r in item["qti_responses"]]
        qti = aggregate(answers, Q)
        fired = evaluate(build_facts(intervals, indices), M)

        ds["lessons"].append({**{f: meta[f] for f in _LESSON_FIELDS}, "silence_source": fonte_silencio,
                              "n_segments": len(segs), "n_intervals": len(intervals),
                              "rules_version": F["rules_version"]})
        for s in segs:
            row = {"lesson_id": lid, **{f: s[f] for f in _SEGMENT_FIELDS}}
            if include_text:
                row["text_pseudonymized"] = s["text_pseudonymized"]
            ds["segments"].append(row)
        # O tempo vem da marca, nunca de `índice × 3 s`: com o relógio que
        # reinicia a cada mudança (rules_version 2.0.0) a enésima marca não
        # começa mais em n × 3 s, e quem calculasse assim exportaria marcas
        # começando depois do fim da aula.
        ds["intervals"] += [{"lesson_id": lid, "interval_index": i, "start_ms": m.start_ms, "category": m.category}
                            for i, m in enumerate(coding.marks)]
        m = transition_matrix(intervals, F)
        ds["matrix"] += [{"lesson_id": lid, "from_category": a + 1, "to_category": b + 1, "count": m[a][b]}
                         for a in range(10) for b in range(10) if m[a][b]]
        ds["indices"] += [{"lesson_id": lid, "index_id": k, "value": v["value"], "reason": v["reason"],
                           "numerator_count": v["numerator_count"], "denominator_count": v["denominator_count"],
                           "validation_status": v["validation_status"]} for k, v in indices.items()]
        ds["qti_responses"] += [{"lesson_id": lid, "response_index": n, **{f"q{i}": a[i] for i in range(1, 25)}}
                                for n, a in enumerate(answers)]
        ds["qti_results"].append({"lesson_id": lid, "response_count": qti["response_count"], "displayable": qti["displayable"],
                                  **{f"oc{i}": (qti["octants"] or {}).get(f"oc{i}") for i in range(1, 9)},
                                  "agency": qti["agency"], "communion": qti["communion"]})
        ds["mtss"] += [{"lesson_id": lid, "rule_id": f["rule_id"], "tier1_dimension": f["tier1_dimension"],
                        "framing": f["framing"], "validation_status": f["validation_status"],
                        "rules_version": f["rules_version"]} for f in fired]
        ds["recommendations"] += [{"lesson_id": lid, "recommendation_id": r["recommendation_id"], "rule_id": r["rule_id"],
                                   "validation_status": r["validation_status"]} for r in recommendations(fired, P)]
        ds["triangulation"] += [{"lesson_id": lid, "pair_id": t["pair_id"], "fias_value": t["fias"]["value"],
                                 "qti_available": t["qti_available"], "qti_values": [q["value"] for q in t["qti"]]}
                                for t in triangulate(intervals, indices, qti, P, Q)]
        processing.append({"lesson_id": lid, **{f: item["processing"].get(f) for f in _PROCESSING_FIELDS},
                           "silence_source": fonte_silencio})
    ds["manifest"] = {"export_version": EXPORT_VERSION, "rules_version": F["rules_version"], "exported_at": exported_at,
                      "include_text": include_text, "lesson_count": len(lessons), "processing": processing}
    return ds


def to_json(dataset: dict) -> str:
    return json.dumps(dataset, ensure_ascii=False, indent=2)


def _cell(v):
    """Serialização determinística de uma célula CSV (mesmo resultado em Web/Android):
    bool -> "true"/"false" minúsculo; None -> célula vazia; list/dict -> JSON compacto
    (ensure_ascii=False); float -> repr() (representação decimal mais curta que
    recupera o valor exato); demais tipos, sem transformação."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return ""
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, float):
        return repr(v)
    return v


def to_csv_files(dataset: dict) -> dict[str, str]:
    files = {}
    for t in TABLES:
        rows = dataset[t]
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(TABLE_FIELDS[t]), lineterminator="\n", restval="")
        w.writeheader()
        w.writerows({k: _cell(v) for k, v in r.items()} for r in rows)
        files[f"{t}.csv"] = buf.getvalue()
    return files


def write_zip(dataset: dict, path: Path) -> None:
    files = to_csv_files(dataset)
    manifest = {**dataset["manifest"],
                "files": {n: hashlib.sha256(c.encode("utf-8")).hexdigest() for n, c in files.items()}}
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, content in files.items():
            z.writestr(name, content.encode("utf-8"))
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
