import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, StringConstraints
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.audio.storage import delete_file
from app.audit import record
from app.auth.deps import Actor, current_admin
from app.auth.passwords import generate_provisional_password, hash_password
from app.auth.routes import me_payload
from app.auth.sessions import delete_all_sessions
from app.aulas.service import aula_summary, soft_delete_aula
from app.core.db import get_db
from app.core.errors import AppError
from app.core.logging import log_event
from app.models import Aula, Disciplina, Professor, Sessao, Turma, utcnow
from app.users.service import create_professor

router = APIRouter(prefix="/admin")


class AgirComoIn(BaseModel):
    professor_id: uuid.UUID


@router.post("/agir-como")
def agir_como(body: AgirComoIn, actor: Actor = Depends(current_admin), db: Session = Depends(get_db)):
    if body.professor_id == actor.user.id:
        raise AppError(422, "AGIR_COMO_PROPRIA_CONTA", "Você já está na sua própria conta.")
    target = db.get(Professor, body.professor_id)
    if target is None or target.deleted_at is not None:
        raise AppError(404, "CONTA_NAO_ENCONTRADA", "Conta não encontrada.")
    actor.session.acting_as_professor_id = target.id
    record(db, admin_id=actor.user.id, professor_id=target.id, resource="professor",
           resource_id=target.id, action="read")
    db.commit()
    log_event("admin_act_as", admin_id=actor.user.id, professor_id=target.id)
    return me_payload(Actor(user=actor.user, session=actor.session, acting_as=target))


@router.delete("/agir-como")
def parar_de_agir(actor: Actor = Depends(current_admin), db: Session = Depends(get_db)):
    actor.session.acting_as_professor_id = None
    db.commit()
    return me_payload(Actor(user=actor.user, session=actor.session, acting_as=None))


DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class ContaIn(BaseModel):
    username: Annotated[str, StringConstraints(max_length=64)]
    display_name: DisplayName
    role: Literal["PROFESSOR", "ADMIN_LOCAL"] = "PROFESSOR"


class ContaPatch(BaseModel):
    display_name: DisplayName | None = None
    is_active: bool | None = None


class ExcluirIn(BaseModel):
    confirmar_username: Annotated[str, StringConstraints(max_length=64)]


def conta_out(p: Professor) -> dict:
    return {"id": str(p.id), "username": p.username, "display_name": p.display_name, "role": p.role,
            "is_active": p.is_active, "must_change_password": p.must_change_password,
            "created_at": p.created_at.isoformat()}


def _get_conta(db: Session, conta_id: uuid.UUID) -> Professor:
    conta = db.get(Professor, conta_id)
    if conta is None or conta.deleted_at is not None:
        raise AppError(404, "CONTA_NAO_ENCONTRADA", "Conta não encontrada.")
    return conta


def _other_active_admins(db: Session, exclude_id: uuid.UUID) -> int:
    return db.scalar(select(func.count()).select_from(Professor).where(
        Professor.role == "ADMIN_LOCAL", Professor.is_active.is_(True), Professor.deleted_at.is_(None),
        Professor.id != exclude_id))


def _protect(db: Session, actor: Actor, conta: Professor, verbo: str) -> None:
    if conta.id == actor.user.id:
        raise AppError(409, "PROPRIA_CONTA", f"Você não pode {verbo} a própria conta.")
    # Defensiva: como um admin nunca pode desativar/excluir a própria conta (guarda acima), o admin
    # que está chamando esta rota é sempre um administrador ativo distinto de "conta" — então esta
    # contagem nunca chega a zero e ULTIMO_ADMIN não é alcançável na prática.
    if conta.role == "ADMIN_LOCAL" and conta.is_active and _other_active_admins(db, conta.id) == 0:
        raise AppError(409, "ULTIMO_ADMIN", "É preciso manter pelo menos um administrador ativo.")


def _record_account_change(db: Session, actor: Actor, conta: Professor, action: str) -> None:
    """Spec §6: toda ação do admin sobre a conta de um professor fica registrada."""
    if conta.role == "PROFESSOR":
        record(db, admin_id=actor.user.id, professor_id=conta.id, resource="professor",
               resource_id=conta.id, action=action)


@router.get("/contas")
def list_contas(actor: Actor = Depends(current_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(Professor).where(Professor.deleted_at.is_(None)).order_by(Professor.display_name))
    return [conta_out(p) for p in rows]


@router.post("/contas", status_code=201)
def create_conta(body: ContaIn, actor: Actor = Depends(current_admin), db: Session = Depends(get_db)):
    senha = generate_provisional_password()
    conta = create_professor(db, username=body.username, display_name=body.display_name, role=body.role,
                             password=senha, must_change_password=True)
    db.commit()
    log_event("account_created", admin_id=actor.user.id, professor_id=conta.id)
    return {"conta": conta_out(conta), "senha_provisoria": senha}


@router.patch("/contas/{conta_id}")
def patch_conta(conta_id: uuid.UUID, body: ContaPatch, actor: Actor = Depends(current_admin),
                db: Session = Depends(get_db)):
    conta = _get_conta(db, conta_id)
    if body.display_name is not None:
        conta.display_name = body.display_name
    if body.is_active is False and conta.is_active:
        _protect(db, actor, conta, "desativar")
        conta.is_active = False
        delete_all_sessions(db, conta.id)
    elif body.is_active is True:
        conta.is_active = True
    _record_account_change(db, actor, conta, "update")
    db.commit()
    return conta_out(conta)


@router.post("/contas/{conta_id}/senha-provisoria")
def reset_senha(conta_id: uuid.UUID, actor: Actor = Depends(current_admin), db: Session = Depends(get_db)):
    conta = _get_conta(db, conta_id)
    senha = generate_provisional_password()
    conta.password_hash = hash_password(senha)
    conta.must_change_password, conta.failed_logins, conta.locked_until = True, 0, None
    delete_all_sessions(db, conta.id)
    _record_account_change(db, actor, conta, "update")
    db.commit()
    log_event("password_reset", admin_id=actor.user.id, professor_id=conta.id)
    return {"senha_provisoria": senha}


@router.delete("/contas/{conta_id}", status_code=204)
def delete_conta(conta_id: uuid.UUID, body: ExcluirIn, actor: Actor = Depends(current_admin),
                 db: Session = Depends(get_db)):
    conta = _get_conta(db, conta_id)
    if conta.id == actor.user.id:
        raise AppError(409, "PROPRIA_CONTA", "Você não pode excluir a própria conta.")
    if body.confirmar_username.strip().lower() != conta.username:
        raise AppError(422, "CONFIRMACAO_INVALIDA", "Digite o nome de usuário da conta para confirmar.")
    _protect(db, actor, conta, "excluir")
    paths: list[str] = []
    for aula in db.scalars(select(Aula).where(Aula.professor_id == conta.id, Aula.deleted_at.is_(None))):
        paths += soft_delete_aula(db, aula)
    now = utcnow()
    for model in (Turma, Disciplina):
        db.execute(update(model).where(model.professor_id == conta.id, model.deleted_at.is_(None))
                   .values(deleted_at=now))
    delete_all_sessions(db, conta.id)
    db.execute(update(Sessao).where(Sessao.acting_as_professor_id == conta.id)
               .values(acting_as_professor_id=None))
    conta.deleted_at, conta.is_active = now, False
    _record_account_change(db, actor, conta, "delete")
    db.commit()
    for rel in paths:
        delete_file(rel)
    log_event("account_deleted", admin_id=actor.user.id, professor_id=conta.id)


@router.get("/aulas")
def list_all_aulas(professor_id: uuid.UUID | None = None, actor: Actor = Depends(current_admin),
                   db: Session = Depends(get_db)):
    query = (select(Aula, Turma, Disciplina, Professor)
             .join(Turma, Turma.id == Aula.turma_id).join(Disciplina, Disciplina.id == Aula.disciplina_id)
             .join(Professor, Professor.id == Aula.professor_id)
             .where(Aula.deleted_at.is_(None), Professor.deleted_at.is_(None))
             .order_by(Aula.lesson_date.desc(), Aula.created_at.desc()))
    if professor_id is not None:
        query = query.where(Aula.professor_id == professor_id)
    rows = db.execute(query).all()
    record(db, admin_id=actor.user.id, professor_id=professor_id, resource="aula", resource_id=None,
           action="read")
    db.commit()
    return [{**aula_summary(a, t, d), "professor": {"id": str(p.id), "display_name": p.display_name}}
            for a, t, d, p in rows]
