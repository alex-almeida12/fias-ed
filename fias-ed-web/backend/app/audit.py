import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AcessoAdmin


def record(db: Session, *, admin_id: uuid.UUID, professor_id: uuid.UUID | None, resource: str,
           resource_id: uuid.UUID | None, action: str) -> None:
    db.add(AcessoAdmin(admin_id=admin_id, professor_id=professor_id, resource=resource,
                       resource_id=resource_id, action=action))


def audit(db: Session, actor, resource: str, resource_id: uuid.UUID | None, action: str) -> None:
    """Registra leitura/alteração do admin sobre dados de outro professor.

    Não faz nada quando o usuário age sobre os próprios dados."""
    if actor.acting_as is None:
        return
    record(db, admin_id=actor.user.id, professor_id=actor.acting_as.id, resource=resource,
           resource_id=resource_id, action=action)


def last_admin_change(db: Session, aula_id: uuid.UUID) -> datetime | None:
    return db.scalar(select(func.max(AcessoAdmin.created_at)).where(
        AcessoAdmin.resource == "aula", AcessoAdmin.resource_id == aula_id, AcessoAdmin.action != "read"))
