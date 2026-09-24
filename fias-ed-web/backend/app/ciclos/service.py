"""O ciclo sabe onde cada aula está. Nenhuma regra científica aqui: posição é
fato de calendário, não de método."""
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Aula, Ciclo

Posicao = Literal["primeira", "primeira_e_ultima", "meio", "ultima", "fora"]


def ciclo_da_aula(db: Session, aula: Aula) -> Ciclo | None:
    return db.execute(
        select(Ciclo).where(Ciclo.turma_id == aula.turma_id,
                            Ciclo.disciplina_id == aula.disciplina_id,
                            Ciclo.deleted_at.is_(None))
        .order_by(Ciclo.iniciado_em.desc())
    ).scalars().first()


def _aulas_do_ciclo(db: Session, ciclo: Ciclo) -> list[Aula]:
    return list(db.execute(
        select(Aula).where(Aula.turma_id == ciclo.turma_id,
                           Aula.disciplina_id == ciclo.disciplina_id,
                           Aula.lesson_date >= ciclo.iniciado_em,
                           Aula.deleted_at.is_(None))
        .order_by(Aula.lesson_date, Aula.created_at)
    ).scalars())


def posicao_no_ciclo(db: Session, aula: Aula) -> Posicao:
    ciclo = ciclo_da_aula(db, aula)
    if ciclo is None:
        return "fora"
    aulas = _aulas_do_ciclo(db, ciclo)
    if not aulas:
        return "fora"
    primeira = aulas[0].id == aula.id
    # A última só existe depois do encerramento: antes disso, qualquer aula pode
    # ainda ser seguida por outra na semana seguinte. Declarar "última" cedo
    # travaria a aula esperando uma coleta que ainda não precisa existir.
    ultima = ciclo.encerrado_em is not None and aulas[-1].id == aula.id
    if primeira and ultima:
        return "primeira_e_ultima"
    if primeira:
        return "primeira"
    if ultima:
        return "ultima"
    return "meio"
