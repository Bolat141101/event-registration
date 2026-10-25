"""Adversarial results which the original probe incorrectly accepted."""

import copy
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "checks"))
from load_probe import validate_result  # noqa: E402


def healthy_result() -> dict[str, Any]:
    return {
        "registration_requests": 200,
        "sse_virtual_clients": 2,
        "registration": {"codes": {202: 200}, "confirmed": 10, "waitlisted": 190},
        "integrity": {"duplicate_emails": 0, "duplicate_queue_numbers": 0},
        "outbox": {"pending": 600},
        "sse": {
            "requested": 2,
            "established": 2,
            "active_before_close": 2,
            "setup_within_20s": True,
            "errors": {},
            "messages": 20,
            "stale_clients": 0,
            "new_deadlocks": 0,
        },
    }


def test_load_probe_accepts_complete_success() -> None:
    validate_result(healthy_result())


@pytest.mark.parametrize(
    ("section", "changes"),
    [
        ("registration", {"codes": {500: 200}, "confirmed": 0, "waitlisted": 0}),
        (
            "registration",
            {"codes": {202: 100, 429: 100}, "confirmed": 10, "waitlisted": 90},
        ),
        ("registration", {"confirmed": 0, "waitlisted": 200}),
        ("outbox", {"pending": 599}),
        ("outbox", {"failed": 1}),
        ("sse", {"new_deadlocks": 1}),
        ("sse", {"established": 1}),
        ("sse", {"messages": 2, "stale_clients": 2}),
        ("sse", {"errors": {"ValueError": 1}}),
    ],
)
def test_load_probe_rejects_partial_or_invalid_success(
    section: str, changes: dict[str, Any]
) -> None:
    result = copy.deepcopy(healthy_result())
    result[section].update(changes)
    with pytest.raises(AssertionError):
        validate_result(result)


def test_load_probe_validates_real_snapshot_contract() -> None:
    import json

    from load_probe import validate_snapshot

    expected = {
        "id": "event-id",
        "confirmed": 10,
        "waitlisted": 190,
        "starts_at": "2030-01-01T12:00:00Z",
    }
    valid = {**expected, "server_time": "2030-01-01T00:00:00Z"}
    validate_snapshot(json.dumps(valid), expected)
    validate_snapshot(json.dumps({**valid, "starts_at": "2030-01-01T12:00:00+00:00"}), expected)
    for invalid in [
        {},
        [],
        "not-json",
        {**valid, "id": "other-event"},
        {**valid, "confirmed": 0},
        {**valid, "starts_at": "2030-01-01T12:00:01Z"},
        {**valid, "confirmed": 10.0},
        {**valid, "server_time": "2030-01-01T00:00:00"},
        {**valid, "server_time": None},
        {**valid, "server_time": "broken"},
        {**valid, "private_token": "fictitious-secret"},
    ]:
        with pytest.raises((ValueError, TypeError)):
            validate_snapshot(json.dumps(invalid), expected)
