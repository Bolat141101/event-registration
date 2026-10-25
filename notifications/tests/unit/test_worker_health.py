import json
import time

import pytest

from notifications_app import worker_health


def test_heartbeat_rejects_stalled_or_database_failed_loop(tmp_path, monkeypatch):
    path = tmp_path / "heartbeat.json"
    monkeypatch.setattr(worker_health, "PATH", path)
    with pytest.raises(SystemExit):
        worker_health.check()
    worker_health.heartbeat(True)
    worker_health.check()
    value = json.loads(path.read_text())
    value["at"] = time.monotonic() - 181
    path.write_text(json.dumps(value))
    with pytest.raises(SystemExit):
        worker_health.check()
    worker_health.heartbeat(False)
    with pytest.raises(SystemExit):
        worker_health.check()
