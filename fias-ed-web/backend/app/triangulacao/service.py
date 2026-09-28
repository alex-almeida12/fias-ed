"""Triangulação FIAS × QTI: pôr lado a lado o que o áudio mostrou (a
codificação FIAS da aula) e o que os estudantes perceberam (o resultado do
QTI), sem classificar e sem dar veredito sobre o professor.

Nenhuma regra científica é implementada aqui: `fias_ed_engine.triangulation.
triangulate` decide os quatro pares, o que cada um compara e a pergunta de
reflexão que acompanha cada um. Este módulo só escolhe as entradas — qual
codificação (via `codificacao_da_aula`, para que a triangulação nunca enxergue
uma aula diferente da que a tela de padrões mostra) e qual coleta QTI vale
para esta aula — e persiste exatamente o que o motor devolveu, inclusive
`validation_status: PENDING_SCIENTIFIC_VALIDATION` em todo par: isso é honesto
e não deve ser escondido.
"""
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from fias_ed_engine.rules import load_rules
from fias_ed_engine.triangulation import triangulate

from app.ciclos.service import ciclo_da_aula
from app.fias.service import codificacao_da_aula
from app.models import Aula, ColetaQTI, IndicadorFIAS, ResultadoQTI, Triangulacao


def coleta_vigente(db: Session, aula: Aula) -> ColetaQTI | None:
    """A coleta mais recente ANTERIOR ou igual à data da aula. Triangular uma
    aula de março contra uma percepção medida em junho seria compará-la com
    uma opinião que ainda não existia quando a aula aconteceu.

    Desempate por created_at e depois por id: a Task 5 fez a reimportação na
    mesma data substituir a anterior, então duas coletas vivas na mesma data
    só surgem por caminho excepcional — mas quando surgirem, a escolha não
    pode depender da ordem em que o banco varreu a tabela."""
    ciclo = ciclo_da_aula(db, aula)
    if ciclo is None:
        return None
    return db.execute(
        select(ColetaQTI).where(ColetaQTI.ciclo_id == ciclo.id,
                                ColetaQTI.coletado_em <= aula.lesson_date,
                                ColetaQTI.deleted_at.is_(None))
        .order_by(ColetaQTI.coletado_em.desc(), ColetaQTI.created_at.desc(), ColetaQTI.id.desc())
    ).scalars().first()


def _qti_result(db: Session, aula: Aula) -> dict:
    coleta = coleta_vigente(db, aula)
    if coleta is None:
        # Caminho que o motor já trata: devolve os 4 pares com qti_available
        # False e value None, mas com a pergunta de reflexão preenchida — sem
        # QTI o professor ainda recebe a pergunta, só não recebe o número.
        return {"displayable": False, "octants": {}}
    resultado = db.scalar(select(ResultadoQTI).where(ResultadoQTI.coleta_id == coleta.id))
    return {"displayable": coleta.displayable, "octants": resultado.octantes}


def triangular(db: Session, aula: Aula) -> list[dict]:
    """Recomputa e grava a triangulação da aula, apagando a anterior — mesmo
    padrão de `gravar_indicadores`/`apagar_resultado_anterior` (app/fias/
    service.py): não duplicar, e nunca deixar evidência antiga fora de
    sincronia com a nova."""
    regras = load_rules("fias_rules")
    codificacao = codificacao_da_aula(db, aula, regras)
    linhas = db.scalars(select(IndicadorFIAS).where(IndicadorFIAS.aula_id == aula.id,
                                                     IndicadorFIAS.deleted_at.is_(None))).all()
    indices = {i.index_id: {"value": i.value} for i in linhas}
    pares = triangulate(codificacao.intervals, indices, _qti_result(db, aula),
                        load_rules("pedagogical_rules"), load_rules("qti_config"))

    db.execute(delete(Triangulacao).where(Triangulacao.aula_id == aula.id))
    for par in pares:
        db.add(Triangulacao(
            aula_id=aula.id, pair_id=par["pair_id"], fias_kind=par["fias"]["kind"],
            fias_ref=par["fias"]["ref"], fias_value=par["fias"]["value"],
            qti_available=par["qti_available"], qti_values=par["qti"],
            reflection_question=par["reflection_question"], source_reference=par["source_reference"],
            validation_status=par["validation_status"]))
    db.commit()
    return pares
