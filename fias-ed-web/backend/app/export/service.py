"""Adaptador do dataset de pesquisa: lê o banco do Web e monta a lista de
aulas que `fias_ed_engine.export.build_dataset` espera.

Nenhum cálculo acontece aqui — quem calcula é o motor. `build_dataset`
recalcula tudo (codificação, índices, MTSS, triangulação, qualificação pelo
QTI) a partir dos dados crus de cada aula, em vez de ler o que o Web já
gravou em `Triangulacao`/`InterpretacaoMTSS`/`RecomendacaoMTSS`; é isso que
garante que o dataset seja reprodutível a partir do que está no banco, e não
um espelho do que a aplicação decidiu mostrar num momento específico. Este
módulo só escolhe as entradas cruas, do mesmo jeito que `codificacao_da_aula`
(app/fias/service.py) e `coleta_vigente` (app/triangulacao/service.py) já
fazem para a tela — reaproveitadas aqui, não reimplementadas, para que o
dataset nunca discorde da tela por ter lido a coleta QTI de outro jeito.

Sem rota HTTP: o botão de exportar é escopo de outra tarefa.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from fias_ed_engine.export import build_dataset

from app.models import Aula, ClassificacaoFIAS, Disciplina, Falante, Processamento, RespostaQTI, Segmento
from app.pipeline.align import fala_detectada
from app.transcricao.service import transcricao_da_aula
from app.triangulacao.service import coleta_vigente

_PROCESSING_FIELDS = ("app_version", "fias_model", "fias_model_hash", "asr_model", "asr_model_hash",
                      "diarization_model", "rules_version")


def _lesson(db: Session, aula: Aula, processamento: Processamento) -> dict:
    disciplina = db.get(Disciplina, aula.disciplina_id)
    return {
        "lesson_id": str(aula.id),
        "lesson_date": aula.lesson_date.isoformat(),
        "disciplina": disciplina.name,
        "turma_id": str(aula.turma_id),
        # Do Processamento gravado por `registrar_processamento`, não de uma
        # nova leitura do Audio: é o mesmo valor que `classificar_aula` usou
        # como `total_ms` ao codificar a aula (app/fias/service.py), e ler o
        # registro em vez de recalculá-lo evita que as duas fontes divirjam.
        "duration_ms": processamento.audio_duration_ms,
        "transcript_source": processamento.transcript_source,
    }


def _segments(db: Session, transcricao_id, *, include_text: bool) -> list[dict]:
    linhas = db.execute(
        select(Segmento, ClassificacaoFIAS, Falante.role)
        .join(ClassificacaoFIAS, ClassificacaoFIAS.segmento_id == Segmento.id)
        .join(Falante, Falante.id == Segmento.falante_id)
        .where(Segmento.transcricao_id == transcricao_id)
        .order_by(Segmento.start_ms)
    ).all()
    out = []
    for seg, cls, role in linhas:
        row = {
            "segment_id": str(seg.id), "start_ms": seg.start_ms, "end_ms": seg.end_ms, "role": role,
            "pred_raw": cls.pred_raw, "pred_role_constrained": cls.pred_role_constrained,
            "confidence": cls.confidence, "uncertain": cls.uncertain,
        }
        if include_text:
            # `seg.text_pseudonymized` pode ser None (segmento nunca
            # pseudonimizado). Não filtrar nem substituir por string vazia
            # aqui: é isto que deixa `build_dataset` decidir — e ele decide
            # levantando ExportPrivacyError, que este módulo nunca captura.
            row["text_pseudonymized"] = seg.text_pseudonymized
        out.append(row)
    return out


def _qti_responses(db: Session, aula: Aula) -> list[dict]:
    coleta = coleta_vigente(db, aula)
    if coleta is None:
        return []
    respostas = db.scalars(
        select(RespostaQTI).where(RespostaQTI.coleta_id == coleta.id, RespostaQTI.deleted_at.is_(None))
        .order_by(RespostaQTI.response_index)
    ).all()
    # `respostas` já está no formato que RespostaQTI.respostas guarda
    # ({"1": 4, ..., "24": 5}) — o mesmo que build_dataset espera em
    # `qti_responses`, sem transformação.
    return [r.respostas for r in respostas]


def montar_dataset(db: Session, aulas: list[Aula], *, include_text: bool, exported_at: str) -> dict:
    itens = []
    for aula in aulas:
        processamento = db.scalar(select(Processamento).where(Processamento.aula_id == aula.id))
        transcricao = transcricao_da_aula(db, aula.id)
        item = {
            "lesson": _lesson(db, aula, processamento),
            "segments": _segments(db, transcricao.id, include_text=include_text),
            "qti_responses": _qti_responses(db, aula),
            "processing": {f: getattr(processamento, f) for f in _PROCESSING_FIELDS},
        }
        # Ausente (None) quando a aula não tem evidência de fala gravada —
        # nunca inventado aqui. `build_dataset` trata `item.get("speech")`
        # como "não se sabe" tanto para chave ausente quanto para None, então
        # não há necessidade de distinguir os dois casos.
        fala = fala_detectada(db, transcricao.id)
        if fala is not None:
            item["speech"] = fala
        itens.append(item)
    return build_dataset(itens, include_text=include_text, exported_at=exported_at)
