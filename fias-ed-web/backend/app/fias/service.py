"""Orquestra a classificação FIAS de uma aula e grava o que o motor do shared
decidiu.

Nenhuma regra científica é implementada aqui: `constrain_by_role`,
`segments_to_intervals` e `compute_indices` (fias_ed_engine) decidem. Este
módulo só produz (segmento, logits, papel) para o motor e persiste
exatamente o que ele devolveu — inclusive a predição crua, que é
rastreabilidade científica (o que o modelo disse antes da restrição por
papel), não redundância.
"""
import hashlib
import platform
import time
import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from fias_ed_engine.classifier import constrain_by_role, divergence_rate
from fias_ed_engine.indices import compute_indices
from fias_ed_engine.intervals import CodedSegment, segments_to_intervals
from fias_ed_engine.rules import load_rules

from app import APP_VERSION
from app.audio.prepare import audio_original
from app.core.config import get_settings
from app.ml.clf_bertimbau import montar_pares
from app.ml.loader import obter_classificador
from app.ml.registry import carregar_registro, entrada
from app.models import (Aula, ClassificacaoFIAS, Falante, IndicadorFIAS, ModeloIA, Processamento,
                        Segmento)
from app.transcricao.service import texto_efetivo, transcricao_da_aula


def _segmentos_com_papel(db: Session, transcricao_id: uuid.UUID) -> list[tuple[Segmento, str]]:
    """Segmento + papel do falante numa consulta só (join), não duas consultas
    independentes: mesma lição de handle_diarize — quando duas listas precisam
    corresponder posição a posição, uma única consulta evita que dois
    segmentos com o mesmo start_ms troquem de papel entre si por causa de
    desempates diferentes em cada consulta."""
    linhas = db.execute(
        select(Segmento, Falante.role)
        .join(Falante, Falante.id == Segmento.falante_id)
        .where(Segmento.transcricao_id == transcricao_id)
        .order_by(Segmento.start_ms)
    ).all()
    return [(seg, papel) for seg, papel in linhas]


def apagar_resultado_anterior(db: Session, transcricao_id: uuid.UUID) -> None:
    """Apaga as ClassificacaoFIAS de uma reclassificação anterior: evidência e
    resultado nunca podem ficar fora de sincronia (spec §3)."""
    segmento_ids = db.scalars(select(Segmento.id).where(Segmento.transcricao_id == transcricao_id)).all()
    if segmento_ids:
        db.execute(delete(ClassificacaoFIAS).where(ClassificacaoFIAS.segmento_id.in_(segmento_ids)))


def gravar_indicadores(db: Session, aula: Aula, indices: dict[str, dict], rules_version: str) -> None:
    """Grava a evidência estruturada que compute_indices devolveu — um índice
    por linha, nunca um JSONB livre. Apaga os indicadores de uma classificação
    anterior antes: mesma regra de não duplicar da ClassificacaoFIAS."""
    db.execute(delete(IndicadorFIAS).where(IndicadorFIAS.aula_id == aula.id))
    for info in indices.values():
        evidencia = info["evidence"]
        db.add(IndicadorFIAS(
            aula_id=aula.id, index_id=info["id"], value=info["value"], reason=info["reason"],
            numerator_count=info["numerator_count"], denominator_count=info["denominator_count"],
            n_intervals=evidencia["n_intervals"], rules_version=rules_version,
            validation_status=info["validation_status"], mean_confidence=evidencia["mean_confidence"]))


def _hardware_device() -> tuple[str, str]:
    """`hardware`/`device` são bookkeeping de infraestrutura para
    reprodutibilidade (spec §44), não ciência do FIAS: não há regra do shared
    para isso. CUDA é detectado só se torch estiver instalado — a suíte roda
    sem torch, então o caminho feliz aqui é sempre "cpu"."""
    hardware = platform.platform() or platform.machine() or "desconhecido"
    device = "cpu"
    try:
        import torch
        if torch.cuda.is_available():
            device = "cuda"
    except ImportError:
        pass
    return hardware, device


def _registrar_modelo_ia(db: Session, model_id: str) -> None:
    """ModeloIA sai inteiro do registro do shared (§66, §67) — nunca de uma
    lista local de hashes. Upsert por model_id: o mesmo modelo usado em várias
    aulas gera uma linha só, atualizada, não uma por aula."""
    m = entrada(model_id)
    pesos = next(a for a in m["artifacts"] if a["role"] == "weights")
    licenca = m["license"]
    valores = dict(
        name=m["name"],
        model_version=carregar_registro()["registry_version"],
        task=m["task"],
        format=m["format"],
        sha256=pesos["sha256"],
        size_bytes=pesos["size_bytes"],
        source=m.get("source_reference", ""),
        license=f"{licenca['weights_base']}; dados: {licenca['training_data']}"[:200],
        parameters=m.get("metrics", {}),
    )
    existente = db.scalar(select(ModeloIA).where(ModeloIA.model_id == model_id))
    if existente is not None:
        for campo, valor in valores.items():
            setattr(existente, campo, valor)
    else:
        db.add(ModeloIA(model_id=model_id, **valores))


def registrar_processamento(db: Session, aula: Aula, *, audio_duration_ms: int, transcript_source: str,
                            stage_times_ms: dict, role_divergence_rate: float | None,
                            rules_version: str) -> None:
    """Grava (ou atualiza, se já existir) o Processamento que torna a
    classificação reproduzível: com qual modelo, quais parâmetros e sob qual
    versão de regras a aula foi analisada (spec §5.4, critério 9, §44)."""
    settings = get_settings()
    fias_registro = entrada(settings.clf_model_id)
    pesos = next(a for a in fias_registro["artifacts"] if a["role"] == "weights")
    # max_length/padding vêm de fias_rules.classifier, nunca de literais — mesmo
    # padrão de app/ml/clf_bertimbau.py (§2.6: padding não é neutro sob quantização).
    classificador = load_rules("fias_rules")["classifier"]
    hardware, device = _hardware_device()
    valores = dict(
        app_version=APP_VERSION,
        rules_version=rules_version,
        asr_model=settings.asr_model_id,
        # Sem registro de hash para ASR/diarização no shared (só o classificador
        # FIAS passa por vetores de conformance lá): um identificador estável a
        # partir do model_id, não um cálculo científico — nunca usado pelo motor,
        # só para saber "o que rodou" quando o modelo em si ganhar um registro.
        asr_model_hash=hashlib.sha256(settings.asr_model_id.encode()).hexdigest(),
        diarization_model=settings.diar_model_id,
        fias_model=fias_registro["model_id"],
        fias_model_hash=pesos["sha256"],
        parameters={
            "asr": {"language": "pt", "temperature": 0.0},
            "classifier": {"max_length": classificador["max_length"], "padding": classificador["padding"],
                          "model_size_bytes": pesos["size_bytes"]},
        },
        hardware=hardware,
        device=device,
        audio_duration_ms=audio_duration_ms,
        transcript_source=transcript_source,
        stage_times_ms=stage_times_ms,
        status="FIAS_COMPLETED",
        role_divergence_rate=role_divergence_rate,
    )
    existente = db.scalar(select(Processamento).where(Processamento.aula_id == aula.id))
    if existente is not None:
        for campo, valor in valores.items():
            setattr(existente, campo, valor)
    else:
        db.add(Processamento(aula_id=aula.id, **valores))
    _registrar_modelo_ia(db, fias_registro["model_id"])


def classificar_aula(db: Session, aula: Aula) -> None:
    inicio = time.monotonic()
    regras = load_rules("fias_rules")
    transcricao = transcricao_da_aula(db, aula.id)
    pares_seg_papel = _segmentos_com_papel(db, transcricao.id)
    segmentos = [seg for seg, _ in pares_seg_papel]
    # texto_efetivo, NUNCA texto_original_asr: usar o bruto do ASR desfaria em
    # silêncio a revisão que o professor acabou de fazer (Task 10).
    lotes = obter_classificador().logits(montar_pares([texto_efetivo(s) for s in segmentos]))

    apagar_resultado_anterior(db, transcricao.id)
    codificados: list[CodedSegment] = []
    predicoes = []
    algum_revisado = False
    for (seg, papel), logits in zip(pares_seg_papel, lotes):
        # constrain_by_role devolve um RolePrediction com EXATAMENTE as cinco
        # colunas que ClassificacaoFIAS exige, já com o deslocamento de
        # categoria e o limiar de incerteza aplicados pelo motor. Persistido
        # como veio — não recalculado, e a predição crua não é descartada.
        predicao = constrain_by_role(logits, papel, regras)
        predicoes.append(predicao)
        revisado = seg.texto_revisado is not None
        algum_revisado = algum_revisado or revisado
        db.add(ClassificacaoFIAS(
            segmento_id=seg.id,
            transcript_source="TRANSCRICAO_REVISADA" if revisado else "ASR_ORIGINAL",
            pred_raw=predicao.pred_raw,
            pred_role_constrained=predicao.pred_role_constrained,
            confidence_raw=predicao.confidence_raw,
            confidence=predicao.confidence,
            uncertain=predicao.uncertain,
            model_id=get_settings().clf_model_id,
            rules_version=regras["rules_version"]))
        codificados.append(CodedSegment(start_ms=seg.start_ms, end_ms=seg.end_ms,
                                        category=predicao.pred_role_constrained))

    audio = audio_original(db, aula.id)
    total_ms = audio.duration_ms if audio is not None else 0
    intervalos = segments_to_intervals(codificados, total_ms=total_ms, rules=regras)
    indices = compute_indices(intervalos, regras, n_segments=len(codificados))
    gravar_indicadores(db, aula, indices, regras["rules_version"])

    stage_times_ms = {"fias_classification_ms": int((time.monotonic() - inicio) * 1000)}
    registrar_processamento(
        db, aula, audio_duration_ms=total_ms,
        transcript_source="TRANSCRICAO_REVISADA" if algum_revisado else "ASR_ORIGINAL",
        stage_times_ms=stage_times_ms, role_divergence_rate=divergence_rate(predicoes),
        rules_version=regras["rules_version"])
