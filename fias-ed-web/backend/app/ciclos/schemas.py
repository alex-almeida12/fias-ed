import uuid
from datetime import date

from pydantic import BaseModel, Field

from app.models import Ciclo


class CicloIn(BaseModel):
    turma_id: uuid.UUID
    disciplina_id: uuid.UUID
    n_aulas_previstas: int = Field(ge=1)
    iniciado_em: date


def ciclo_out(c: Ciclo) -> dict:
    return {
        "id": str(c.id),
        "turma_id": str(c.turma_id),
        "disciplina_id": str(c.disciplina_id),
        "professor_id": str(c.professor_id),
        "n_aulas_previstas": c.n_aulas_previstas,
        "iniciado_em": c.iniciado_em.isoformat(),
        "encerrado_em": c.encerrado_em.isoformat() if c.encerrado_em else None,
    }
