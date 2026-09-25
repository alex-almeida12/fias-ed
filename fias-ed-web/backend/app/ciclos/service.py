"""O ciclo sabe onde cada aula está. Nenhuma regra científica aqui: posição é
fato de calendário, não de método."""
import uuid
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Aula, Ciclo

Posicao = Literal["primeira", "primeira_e_ultima", "meio", "ultima", "fora"]


def ciclo_da_aula(db: Session, aula: Aula) -> Ciclo | None:
    return db.execute(
        select(Ciclo).where(Ciclo.turma_id == aula.turma_id,
                            Ciclo.disciplina_id == aula.disciplina_id,
                            Ciclo.deleted_at.is_(None))
        .order_by(Ciclo.iniciado_em.desc())
    ).scalars().first()


# actor: sem tipo declarado (Actor, app.auth.deps) de propósito — declarar o
# tipo criaria import circular, porque app.auth.deps depende (transitivamente)
# de módulos que acabam importando app.ciclos.service. Mesmo padrão de
# get_owned_aula (app/aulas/service.py).
def ciclo_do_professor(db: Session, actor, ciclo_id: uuid.UUID) -> Ciclo:
    """Posse do ciclo — antes desta função existia como `_owned_ciclo`,
    duplicada linha por linha em app/ciclos/routes.py e app/qti/routes.py.
    404 e não 403: o padrão do projeto é não revelar existência a quem não é
    dono."""
    c = db.get(Ciclo, ciclo_id)
    if c is None or c.deleted_at is not None or c.professor_id != actor.effective_professor_id:
        raise AppError(404, "CICLO_NAO_ENCONTRADO", "Ciclo não encontrado.")
    return c


def aulas_do_ciclo(db: Session, ciclo: Ciclo) -> list[Aula]:
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
    aulas = aulas_do_ciclo(db, ciclo)
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
