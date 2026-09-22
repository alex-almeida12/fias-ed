import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.models import Professor


def test_app_user_cannot_run_ddl(db):
    with pytest.raises(DBAPIError):
        db.execute(text("CREATE TABLE invasora (id int)"))
    db.rollback()


def test_app_user_can_write_rows(db):
    db.add(Professor(username="ana", display_name="Ana", role="PROFESSOR", password_hash="x"))
    db.commit()
    assert db.query(Professor).count() == 1


def test_database_rejects_invalid_enum(db):
    with pytest.raises(IntegrityError):
        db.execute(text(
            "INSERT INTO professor (id, created_at, updated_at, version, sync_status, device_id,"
            " username, display_name, role, password_hash, is_active, must_change_password, failed_logins)"
            " VALUES (gen_random_uuid(), now(), now(), 1, 'LOCAL_ONLY', 'x', 'b', 'B', 'CHEFE', 'x',"
            " true, false, 0)"))
    db.rollback()


def test_base_fields_have_defaults(db):
    p = Professor(username="caio", display_name="Caio", role="PROFESSOR", password_hash="x")
    db.add(p)
    db.commit()
    assert p.version == 1 and p.sync_status == "LOCAL_ONLY" and p.device_id and p.deleted_at is None
