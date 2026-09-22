from datetime import date

from app.auth.passwords import hash_password
from app.models import Aula, Disciplina, Escola, Professor, Turma

PASSWORD = "senha-de-teste-123"
_HASH = hash_password(PASSWORD)


def make_user(db, username: str, role: str = "PROFESSOR", *, password: str = PASSWORD,
              must_change: bool = False, active: bool = True) -> Professor:
    user = Professor(username=username, display_name=username.title(), role=role,
                     password_hash=_HASH if password == PASSWORD else hash_password(password),
                     must_change_password=must_change, is_active=active)
    db.add(user)
    db.commit()
    return user


def login(client, username: str, password: str = PASSWORD):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    client.headers["X-CSRF-Token"] = client.cookies["fias_csrf"]
    return r


def make_aula(db, professor, status: str = "DRAFT") -> Aula:
    escola = Escola(name="Escola Teste", name_key="escola teste")
    db.add(escola)
    db.flush()
    turma = Turma(escola_id=escola.id, professor_id=professor.id, name="9º Ano B")
    disciplina = Disciplina(professor_id=professor.id, name="Matemática")
    db.add_all([turma, disciplina])
    db.flush()
    aula = Aula(professor_id=professor.id, turma_id=turma.id, disciplina_id=disciplina.id,
                lesson_date=date(2026, 9, 22), status=status)
    db.add(aula)
    db.commit()
    return aula
