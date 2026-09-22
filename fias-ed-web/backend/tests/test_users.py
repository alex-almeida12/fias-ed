import pytest

from app.auth.passwords import (generate_provisional_password, hash_password, needs_rehash,
                                verify_password)
from app.core.errors import AppError
from app.models import Professor
from app.users.service import create_professor, normalize_username, validate_password


def test_hash_is_argon2id_and_verifies():
    h = hash_password("uma-senha-bem-longa")
    assert h.startswith("$argon2id$")
    assert verify_password(h, "uma-senha-bem-longa")
    assert not verify_password(h, "outra-senha-longa")
    assert not needs_rehash(h)


def test_verify_handles_garbage_hash():
    assert not verify_password("não-é-hash", "qualquer")


def test_provisional_password_is_long_and_random():
    a, b = generate_provisional_password(), generate_provisional_password()
    assert len(a) >= 16 and a != b


@pytest.mark.parametrize("raw,expected", [(" Ana.Silva ", "ana.silva"), ("prof_01", "prof_01")])
def test_normalize_username(raw, expected):
    assert normalize_username(raw) == expected


@pytest.mark.parametrize("raw", ["ab", "com espaço", "ç", "x" * 65, "a/b"])
def test_normalize_username_rejects(raw):
    with pytest.raises(AppError) as e:
        normalize_username(raw)
    assert e.value.code == "USERNAME_INVALID"


def test_validate_password_min_length():
    with pytest.raises(AppError) as e:
        validate_password("curta")
    assert e.value.code == "PASSWORD_TOO_SHORT"
    validate_password("x" * 12)


def test_create_professor_and_duplicate(db):
    p = create_professor(db, username="Ana", display_name="Ana Souza", role="PROFESSOR",
                         password="senha-muito-segura", must_change_password=True)
    db.commit()
    assert p.username == "ana" and p.must_change_password and p.password_hash.startswith("$argon2id$")
    with pytest.raises(AppError) as e:
        create_professor(db, username="ana", display_name="Outra", role="PROFESSOR",
                         password="senha-muito-segura", must_change_password=False)
    assert e.value.code == "USERNAME_TAKEN" and e.value.status == 409


def test_cli_create_admin(db, monkeypatch, capsys):
    from app import cli
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    answers = iter(["senha-do-admin-123", "senha-do-admin-123"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": next(answers))
    assert cli.main(["create-admin", "--username", "pesquisador", "--display-name", "Pesquisador"]) == 0
    admin = db.query(Professor).filter_by(username="pesquisador").one()
    assert admin.role == "ADMIN_LOCAL" and not admin.must_change_password
    assert "senha-do-admin-123" not in capsys.readouterr().out


def test_cli_rejects_mismatched_passwords(db, monkeypatch):
    from app import cli
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    answers = iter(["senha-do-admin-123", "senha-diferente-456"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": next(answers))
    assert cli.main(["create-admin", "--username", "x-admin", "--display-name", "X"]) == 1
    assert db.query(Professor).count() == 0


def test_cli_create_admin_non_tty_reads_stdin(db, monkeypatch, capsys):
    import io

    from app import cli
    monkeypatch.setattr(cli.sys, "stdin", io.StringIO("senha-do-admin-123\nsenha-do-admin-123\n"))
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
    assert cli.main(["create-admin", "--username", "pesquisador2", "--display-name", "Pesquisador 2"]) == 0
    admin = db.query(Professor).filter_by(username="pesquisador2").one()
    assert admin.role == "ADMIN_LOCAL" and not admin.must_change_password
    assert "senha-do-admin-123" not in capsys.readouterr().out


def test_cli_non_tty_rejects_mismatched_passwords(db, monkeypatch):
    import io

    from app import cli
    monkeypatch.setattr(cli.sys, "stdin", io.StringIO("senha-do-admin-123\nsenha-diferente-456\n"))
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
    assert cli.main(["create-admin", "--username", "y-admin", "--display-name", "Y"]) == 1
    assert db.query(Professor).count() == 0
