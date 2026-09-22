from datetime import timedelta

from fastapi import Depends

from app.auth.deps import Actor, current_actor
from app.auth.passwords import verify_password
from app.models import Professor, Sessao, utcnow
from tests.helpers import PASSWORD, login, make_user


def test_login_sets_secure_cookies(client, db):
    make_user(db, "ana")
    r = client.post("/api/auth/login", json={"username": "Ana", "password": PASSWORD})
    assert r.status_code == 200
    assert r.json()["username"] == "ana" and r.json()["acting_as"] is None
    cookies = r.headers.get_list("set-cookie")
    session_cookie = next(c for c in cookies if c.startswith("fias_session="))
    csrf_cookie = next(c for c in cookies if c.startswith("fias_csrf="))
    for flag in ("HttpOnly", "Secure", "SameSite=strict", "Path=/"):
        assert flag.lower() in session_cookie.lower()
    assert "httponly" not in csrf_cookie.lower()
    token = session_cookie.split(";")[0].split("=", 1)[1]
    row = db.query(Sessao).one()
    assert row.token_sha256 != token and len(row.token_sha256) == 64


def test_wrong_password_and_unknown_user_same_message(client, db):
    make_user(db, "ana")
    a = client.post("/api/auth/login", json={"username": "ana", "password": "errada-errada-1"})
    b = client.post("/api/auth/login", json={"username": "ninguem", "password": "errada-errada-1"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json() == {"error_code": "LOGIN_FAILED", "message": "Usuário ou senha incorretos."}


def test_lockout_after_five_failures(client, db):
    make_user(db, "ana")
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "ana", "password": "errada-errada-1"})
    r = client.post("/api/auth/login", json={"username": "ana", "password": PASSWORD})
    assert r.status_code == 401
    user = db.query(Professor).filter_by(username="ana").one()
    db.refresh(user)
    user.locked_until = utcnow() - timedelta(seconds=1)
    db.commit()
    assert client.post("/api/auth/login", json={"username": "ana", "password": PASSWORD}).status_code == 200


def test_inactive_user_cannot_login(client, db):
    make_user(db, "ana", active=False)
    assert client.post("/api/auth/login", json={"username": "ana", "password": PASSWORD}).status_code == 401


def test_me_requires_session(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401 and r.json()["error_code"] == "UNAUTHENTICATED"


def test_forged_session_cookie_rejected(client):
    client.cookies.set("fias_session", "forjado")
    assert client.get("/api/auth/me").status_code == 401


def test_idle_expiry(client, db):
    make_user(db, "ana")
    login(client, "ana")
    s = db.query(Sessao).one()
    s.last_seen_at = utcnow() - timedelta(minutes=121)
    db.commit()
    assert client.get("/api/auth/me").status_code == 401
    assert db.query(Sessao).count() == 0


def test_absolute_expiry(client, db):
    make_user(db, "ana")
    login(client, "ana")
    s = db.query(Sessao).one()
    s.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    assert client.get("/api/auth/me").status_code == 401


def test_logout_invalidates_session(client, db):
    make_user(db, "ana")
    login(client, "ana")
    assert client.post("/api/auth/logout").status_code == 204
    assert db.query(Sessao).count() == 0
    assert client.get("/api/auth/me").status_code == 401


def test_mutation_without_csrf_rejected(client, db):
    make_user(db, "ana")
    login(client, "ana")
    del client.headers["X-CSRF-Token"]
    r = client.post("/api/auth/logout")
    assert r.status_code == 403 and r.json()["error_code"] == "CSRF_INVALID"
    client.headers["X-CSRF-Token"] = "valor-errado"
    assert client.post("/api/auth/logout").status_code == 403


def test_password_change_invalidates_other_sessions(client_factory, db):
    make_user(db, "ana")
    a, b = client_factory(), client_factory()
    login(a, "ana")
    login(b, "ana")
    r = a.post("/api/auth/password", json={"current_password": PASSWORD, "new_password": "nova-senha-segura-1"})
    assert r.status_code == 200
    assert a.get("/api/auth/me").status_code == 200  # nova sessão emitida para quem trocou
    assert b.get("/api/auth/me").status_code == 401


def test_password_change_requires_current_password(client, db):
    make_user(db, "ana")
    login(client, "ana")
    r = client.post("/api/auth/password", json={"current_password": "errada-errada-1", "new_password": "nova-senha-segura-1"})
    assert r.status_code == 401 and r.json()["error_code"] == "PASSWORD_WRONG"


def test_must_change_password_blocks_other_routes(app_instance, client, db):
    @app_instance.get("/api/_pronto")
    def pronto(actor: Actor = Depends(current_actor)):
        return {"ok": True}

    make_user(db, "ana", must_change=True)
    login(client, "ana")
    assert client.get("/api/auth/me").json()["must_change_password"] is True
    r = client.get("/api/_pronto")
    assert r.status_code == 403 and r.json()["error_code"] == "PASSWORD_CHANGE_REQUIRED"
    client.post("/api/auth/password", json={"current_password": PASSWORD, "new_password": "nova-senha-segura-1"})
    client.headers["X-CSRF-Token"] = client.cookies["fias_csrf"]
    assert client.get("/api/_pronto").status_code == 200


def test_login_rehashes_password_when_needs_rehash(client, db, monkeypatch):
    # Ruling P11: prova de que a senha é reidratada (rehash) no login bem-sucedido
    # quando needs_rehash indica que o hash armazenado está desatualizado.
    from app.auth import routes as auth_routes

    make_user(db, "ana")
    old_hash = db.query(Professor).filter_by(username="ana").one().password_hash
    monkeypatch.setattr(auth_routes, "needs_rehash", lambda stored_hash: True)

    r = client.post("/api/auth/login", json={"username": "ana", "password": PASSWORD})
    assert r.status_code == 200

    user = db.query(Professor).filter_by(username="ana").one()
    db.refresh(user)
    assert user.password_hash != old_hash
    assert verify_password(user.password_hash, PASSWORD)
