import time

from app.jobs import worker


def test_beat_touches_file(tmp_path, monkeypatch):
    target = tmp_path / "hb"
    monkeypatch.setattr(worker, "HEARTBEAT_FILE", target)
    worker.beat()
    assert target.exists() and time.time() - target.stat().st_mtime < 5
