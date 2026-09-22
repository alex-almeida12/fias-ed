from app.auth.passwords import hash_password
from app.models import Professor

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
