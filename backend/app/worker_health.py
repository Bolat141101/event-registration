"""Container-local heartbeat: process alive is different from database readiness."""

import json
import os
import time
from pathlib import Path

PATH = Path("/tmp/worker-heartbeat.json")


def heartbeat(ready: bool) -> None:
    temporary = PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps({"pid": os.getpid(), "at": time.monotonic(), "ready": ready}))
    temporary.replace(PATH)


def check() -> None:
    try:
        value = json.loads(PATH.read_text())
        os.kill(value["pid"], 0)
        if not value["ready"] or not 0 <= time.monotonic() - value["at"] < 180:
            raise ValueError("stale heartbeat")
    except (OSError, ValueError, KeyError, TypeError):
        raise SystemExit("Worker heartbeat unavailable, stale, or database not ready") from None
    print("Worker loop is alive and database was ready at its last iteration")


if __name__ == "__main__":
    check()
