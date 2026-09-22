import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.audit import audit
from app.auth.deps import Actor, current_actor, current_admin
from app.catalog.names import name_key
from app.core.db import get_db
from app.core.errors import AppError
from app.models import Disciplina, Escola, Turma, utcnow

router = APIRouter()

Name120 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Name200 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Municipio = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]
Regiao = Literal["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"]


class EscolaIn(BaseModel):
    name: Name200
    municipality: Municipio | None = None
    region: Regiao | None = None
    confirmar_nova: bool = False


class EscolaPatch(BaseModel):
    name: Name200 | None = None
    municipality: Municipio | None = None
    region: Regiao | None = None


class JuntarIn(BaseModel):
    destino_id: uuid.UUID


class TurmaIn(BaseModel):
    name: Name120
    escola_id: uuid.UUID
    school_year: int | None = Field(default=None, ge=1900, le=2100)
    level: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] | None = None


class DisciplinaIn(BaseModel):
    name: Name120


def escola_out(e: Escola) -> dict:
    return {"id": str(e.id), "name": e.name, "municipality": e.municipality, "region": e.region}


def turma_out(t: Turma, e: Escola) -> dict:
    return {"id": str(t.id), "name": t.name, "school_year": t.school_year, "level": t.level,
            "escola": escola_out(e)}


def disciplina_out(d: Disciplina) -> dict:
    return {"id": str(d.id), "name": d.name}


def _active_escola(db: Session, escola_id: uuid.UUID) -> Escola | None:
    e = db.get(Escola, escola_id)
    return e if e is not None and e.deleted_at is None else None


@router.get("/escolas")
def list_escolas(actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    rows = db.scalars(select(Escola).where(Escola.deleted_at.is_(None)).order_by(Escola.name))
    return [escola_out(e) for e in rows]


@router.post("/escolas", status_code=201)
def create_escola(body: EscolaIn, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    key, municipality = name_key(body.name), (body.municipality or None)
    if not body.confirmar_nova:
        same_name = db.scalars(select(Escola).where(Escola.name_key == key, Escola.deleted_at.is_(None)))
        duplicates = [e for e in same_name if name_key(e.municipality or "") == name_key(municipality or "")]
        if duplicates:
            raise AppError(409, "ESCOLA_DUPLICADA", "Já existe uma escola com este nome neste município.",
                           duplicatas=[escola_out(e) for e in duplicates])
    escola = Escola(name=body.name, name_key=key, municipality=municipality, region=body.region)
    db.add(escola)
    db.commit()
    return escola_out(escola)


@router.get("/turmas")
def list_turmas(actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    rows = db.execute(select(Turma, Escola).join(Escola, Escola.id == Turma.escola_id).where(
        Turma.professor_id == actor.effective_professor_id, Turma.deleted_at.is_(None)).order_by(Turma.name)).all()
    audit(db, actor, "turma", None, "read")
    db.commit()
    return [turma_out(t, e) for t, e in rows]


@router.post("/turmas", status_code=201)
def create_turma(body: TurmaIn, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    escola = _active_escola(db, body.escola_id)
    if escola is None:
        raise AppError(422, "ESCOLA_INVALIDA", "Escolha uma escola da lista ou cadastre uma nova.")
    turma = Turma(escola_id=escola.id, professor_id=actor.effective_professor_id, name=body.name,
                  school_year=body.school_year, level=body.level or None)
    db.add(turma)
    db.flush()
    audit(db, actor, "turma", turma.id, "create")
    db.commit()
    return turma_out(turma, escola)


@router.get("/disciplinas")
def list_disciplinas(actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    rows = db.scalars(select(Disciplina).where(Disciplina.professor_id == actor.effective_professor_id,
                                               Disciplina.deleted_at.is_(None)).order_by(Disciplina.name))
    result = [disciplina_out(d) for d in rows]
    audit(db, actor, "disciplina", None, "read")
    db.commit()
    return result


@router.post("/disciplinas", status_code=201)
def create_disciplina(body: DisciplinaIn, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    disciplina = Disciplina(professor_id=actor.effective_professor_id, name=body.name)
    db.add(disciplina)
    db.flush()
    audit(db, actor, "disciplina", disciplina.id, "create")
    db.commit()
    return disciplina_out(disciplina)


@router.patch("/admin/escolas/{escola_id}")
def patch_escola(escola_id: uuid.UUID, body: EscolaPatch, actor: Actor = Depends(current_admin),
                 db: Session = Depends(get_db)):
    escola = _active_escola(db, escola_id)
    if escola is None:
        raise AppError(404, "ESCOLA_NAO_ENCONTRADA", "Escola não encontrada.")
    changes = body.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"]:
        escola.name, escola.name_key = changes["name"], name_key(changes["name"])
    if "municipality" in changes:
        escola.municipality = changes["municipality"] or None
    if "region" in changes:
        escola.region = changes["region"]
    db.commit()
    return escola_out(escola)


@router.post("/admin/escolas/{escola_id}/juntar")
def juntar_escolas(escola_id: uuid.UUID, body: JuntarIn, actor: Actor = Depends(current_admin),
                   db: Session = Depends(get_db)):
    if escola_id == body.destino_id:
        raise AppError(422, "JUNCAO_INVALIDA", "Escolha uma escola diferente para manter.")
    origem, destino = _active_escola(db, escola_id), _active_escola(db, body.destino_id)
    if origem is None or destino is None:
        raise AppError(404, "ESCOLA_NAO_ENCONTRADA", "Escola não encontrada.")
    db.execute(update(Turma).where(Turma.escola_id == origem.id).values(escola_id=destino.id))
    origem.deleted_at = utcnow()
    db.commit()
    return escola_out(destino)
