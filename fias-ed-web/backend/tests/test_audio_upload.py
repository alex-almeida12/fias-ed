import hashlib
import stat
import uuid

import pytest

from app.audio.routes import sanitize_filename
from app.audio.storage import store_root
from app.core.config import get_settings
from app.models import Audio, AudioUpload
from tests.audio_fixtures import make_audio, upload
from tests.helpers import login, make_aula, make_user


@pytest.mark.parametrize("raw,clean", [
    ("aula%201.wav", "aula 1.wav"),
    ("..%2F..%2Fetc%2Fpasswd.wav", "passwd.wav"),
    ("..%5C..%5Cwin.ini.mp3", "win.ini.mp3"),
    ("%00%0A.wav", "wav"),
    ("", "audio"),
])
def test_sanitize_filename(raw, clean):
    assert sanitize_filename(raw) == clean


def test_upload_success(client, db, tmp_path):
    ana = make_user(db, "ana")
    aula = make_aula(db, ana)
    login(client, "ana")
    src = make_audio(tmp_path / "gravação.wav")
    r = upload(client, aula.id, src)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "AUDIO_IMPORTED"
    assert body["upload_pendente"] == {"original_filename": "gravação.wav", "size_bytes": src.stat().st_size}
    row = db.query(AudioUpload).one()
    stored = store_root() / row.path
    assert row.path.startswith("original/") and row.internal_filename.endswith(".wav")
    assert uuid.UUID(row.internal_filename.split(".")[0])
    assert row.sha256 == hashlib.sha256(src.read_bytes()).hexdigest()
    assert not stored.stat().st_mode & stat.S_IWUSR
    assert list((store_root() / "tmp").iterdir()) == []


def test_traversal_name_never_used_as_path(client, db, tmp_path):
    ana = make_user(db, "ana")
    aula = make_aula(db, ana)
    login(client, "ana")
    r = upload(client, aula.id, make_audio(tmp_path / "x.wav"), filename="../../etc/passwd.wav")
    assert r.status_code == 201
    row = db.query(AudioUpload).one()
    assert row.original_filename == "passwd.wav" and ".." not in row.path


def test_unsupported_extension(client, db, tmp_path):
    ana = make_user(db, "ana")
    aula = make_aula(db, ana)
    login(client, "ana")
    r = upload(client, aula.id, make_audio(tmp_path / "x.wav"), filename="virus.exe")
    assert r.status_code == 415 and r.json()["error_code"] == "AUDIO_UNSUPPORTED_FORMAT"


def test_too_large_rejected_and_cleaned(client, db, tmp_path, monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "1000")
    get_settings.cache_clear()
    ana = make_user(db, "ana")
    aula = make_aula(db, ana)
    login(client, "ana")
    r = upload(client, aula.id, make_audio(tmp_path / "x.wav"))
    assert r.status_code == 413 and r.json()["error_code"] == "AUDIO_TOO_LARGE"
    assert db.query(AudioUpload).count() == 0
    assert not (store_root() / "tmp").exists() or list((store_root() / "tmp").iterdir()) == []


def test_empty_file_rejected(client, db):
    ana = make_user(db, "ana")
    aula = make_aula(db, ana)
    login(client, "ana")
    r = client.put(f"/api/aulas/{aula.id}/audio", content=b"", headers={"X-Filename": "a.wav"})
    assert r.status_code == 422 and r.json()["error_code"] == "AUDIO_EMPTY"


def test_replacement_deletes_previous_files(client, db, tmp_path):
    ana = make_user(db, "ana")
    aula = make_aula(db, ana)
    login(client, "ana")
    upload(client, aula.id, make_audio(tmp_path / "a.wav"))
    first = db.query(AudioUpload).one().path
    upload(client, aula.id, make_audio(tmp_path / "b.wav", seconds=70))
    db.expire_all()
    rows = db.query(AudioUpload).all()
    assert len(rows) == 1 and rows[0].path != first
    assert not (store_root() / first).exists()


def test_replacement_soft_deletes_validated_audio(client, db, tmp_path):
    ana = make_user(db, "ana")
    aula = make_aula(db, ana, status="AUDIO_VALIDATED")
    (store_root() / "original").mkdir(parents=True, exist_ok=True)
    (store_root() / "original" / "velho.wav").write_bytes(b"x")
    db.add(Audio(aula_id=aula.id, original_filename="velho.wav", internal_filename=f"{uuid.uuid4()}.wav",
                 path="original/velho.wav", mime_type="audio/wav", size_bytes=1, duration_ms=61000,
                 sha256="0" * 64, channels=1, sample_rate=16000, is_original=True))
    db.commit()
    login(client, "ana")
    r = upload(client, aula.id, make_audio(tmp_path / "novo.wav"))
    assert r.status_code == 201 and r.json()["status"] == "AUDIO_IMPORTED" and r.json()["audio"] is None
    assert not (store_root() / "original" / "velho.wav").exists()


def test_upload_locked_after_analysis_started(client, db, tmp_path):
    ana = make_user(db, "ana")
    aula = make_aula(db, ana, status="TRANSCRIBING")
    login(client, "ana")
    r = upload(client, aula.id, make_audio(tmp_path / "x.wav"))
    assert r.status_code == 409 and r.json()["error_code"] == "AUDIO_LOCKED"


def test_upload_to_other_professor_aula_is_404(client, db, tmp_path):
    make_user(db, "ana")
    aula = make_aula(db, make_user(db, "bia"))
    login(client, "ana")
    assert upload(client, aula.id, make_audio(tmp_path / "x.wav")).status_code == 404


def test_playback_requires_validated_audio_and_supports_range(client, db):
    ana = make_user(db, "ana")
    aula = make_aula(db, ana, status="AUDIO_VALIDATED")
    login(client, "ana")
    assert client.get(f"/api/aulas/{aula.id}/audio").status_code == 404
    (store_root() / "original").mkdir(parents=True, exist_ok=True)
    (store_root() / "original" / "ok.wav").write_bytes(b"0123456789")
    db.add(Audio(aula_id=aula.id, original_filename="ok.wav", internal_filename=f"{uuid.uuid4()}.wav",
                 path="original/ok.wav", mime_type="audio/wav", size_bytes=10, duration_ms=61000,
                 sha256="0" * 64, channels=1, sample_rate=16000, is_original=True))
    db.commit()
    r = client.get(f"/api/aulas/{aula.id}/audio")
    assert r.status_code == 200 and r.headers["content-type"].startswith("audio/wav")
    r = client.get(f"/api/aulas/{aula.id}/audio", headers={"Range": "bytes=0-3"})
    assert r.status_code == 206 and r.content == b"0123"
