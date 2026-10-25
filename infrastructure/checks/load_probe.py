"""Reproducible isolated load probe. Run inside Core's one-off container, never production."""

import asyncio
import json
import os
import statistics
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import Settings
from app.db.session import build_engine


def validate_result(result: dict[str, Any]) -> None:
    registration = result["registration"]
    total = result["registration_requests"]
    assert total == 200 and registration["codes"] == {202: total}, "Registration requests failed"
    assert (registration["confirmed"], registration["waitlisted"]) == (
        10,
        total - 10,
    ), "Capacity/FIFO totals differ"
    assert result["integrity"] == {
        "duplicate_emails": 0,
        "duplicate_queue_numbers": 0,
    }, "Duplicate records"
    assert result["outbox"] == {"pending": total * 3}, "Outbox tasks missing or unexpected status"
    sse = result["sse"]
    assert sse["requested"] == result["sse_virtual_clients"], "Wrong SSE population"
    assert sse["setup_within_20s"], "SSE setup incomplete"
    assert sse["established"] == sse["active_before_close"] == sse["requested"], "SSE disconnected"
    assert not sse["errors"] and sse["stale_clients"] == 0, "SSE failed or stopped updating"
    assert sse["messages"] >= 2 * sse["requested"], "SSE snapshots missing"
    assert sse["new_deadlocks"] == 0, "Database deadlocks detected"


def validate_snapshot(data: str, expected: dict[str, Any]) -> None:
    snapshot = json.loads(data)
    if not isinstance(snapshot, dict) or set(snapshot) != set(expected) | {"server_time"}:
        raise ValueError("Invalid SSE fields")
    for key, value in expected.items():
        actual = snapshot[key]
        if type(actual) is not type(value):
            raise ValueError("Invalid SSE value type")
        # REST/Pydantic uses Z, SSE/jsonable_encoder can use +00:00.
        equal = (
            datetime.fromisoformat(actual) == datetime.fromisoformat(value)
            if key == "starts_at"
            else actual == value
        )
        if not equal:
            raise ValueError("SSE state differs from acknowledged event")
    server_time = snapshot["server_time"]
    if not isinstance(server_time, str):
        raise ValueError("Invalid SSE server time")
    parsed = datetime.fromisoformat(server_time)
    if parsed.utcoffset() is None:
        raise ValueError("Missing SSE server timezone")


async def probe(settings: Settings, engine: AsyncEngine) -> None:
    project = os.environ["LOAD_PROJECT"]
    if not project.startswith("event-registration-relay-check-ui-"):
        raise SystemExit("An isolated UI test project is required")
    auth = {"Authorization": "Bearer " + settings.organizer_token.get_secret_value()}
    tag = uuid4().hex[:10]
    visitors = int(os.environ.get("LOAD_VISITORS", "100"))
    assert 1 <= visitors <= 2000
    result: dict[str, Any] = {
        "label": os.environ.get("LOAD_LABEL", "sample"),
        "sse_virtual_clients": visitors,
        "duration_seconds": 8,
        "registration_requests": 200,
    }
    async with httpx.AsyncClient(
        base_url="http://api:8000",
        timeout=30,
        limits=httpx.Limits(max_connections=max(300, visitors + 10)),
    ) as client:

        async def create(capacity: int) -> str:
            response = await client.post(
                "/api/events",
                headers=auth,
                json={
                    "description": "Load probe " + tag,
                    "capacity": capacity,
                    "starts_at": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
                },
            )
            response.raise_for_status()
            return str(response.json()["id"])

        async def stats() -> tuple[int, int]:
            async with engine.connect() as connection:
                row = (
                    await connection.execute(
                        text(
                            "SELECT xact_commit, deadlocks FROM pg_stat_database "
                            "WHERE datname=current_database()"
                        )
                    )
                ).one()
                return int(row[0]), int(row[1])

        identity = await create(10)
        latencies: list[float] = []
        codes: dict[int, int] = {}
        lock_samples: list[int] = []
        stop = asyncio.Event()

        async def sample_locks() -> None:
            while not stop.is_set():
                async with engine.connect() as connection:
                    value = await connection.scalar(
                        text(
                            "SELECT count(*) FROM pg_stat_activity "
                            "WHERE datname=current_database() "
                            "AND wait_event_type='Lock'"
                        )
                    )
                    lock_samples.append(int(value or 0))
                await asyncio.sleep(0.05)

        async def register(index: int) -> None:
            started = time.perf_counter()
            response = await client.post(
                f"/api/events/{identity}/registrations",
                json={"email": f"load+{tag}-{index}@example.test"},
            )
            latencies.append((time.perf_counter() - started) * 1000)
            codes[response.status_code] = codes.get(response.status_code, 0) + 1

        sampler = asyncio.create_task(sample_locks())
        start = time.perf_counter()
        try:
            await asyncio.gather(*(register(i) for i in range(200)))
        finally:
            stop.set()
            await sampler
        duration = time.perf_counter() - start
        response = await client.get(f"/api/events/{identity}")
        response.raise_for_status()
        snapshot = response.json()
        assert snapshot["confirmed"] <= 10
        assert snapshot["confirmed"] + snapshot["waitlisted"] == codes.get(202, 0)
        result["registration"] = {
            "codes": codes,
            "elapsed_seconds": round(duration, 3),
            "requests_per_second": round(200 / duration, 2),
            "p50_ms": round(statistics.median(latencies), 2),
            "p95_ms": round(sorted(latencies)[int(len(latencies) * 0.95) - 1], 2),
            "p99_ms": round(sorted(latencies)[int(len(latencies) * 0.99) - 1], 2),
            "max_lock_waiters": max(lock_samples, default=0),
            "confirmed": snapshot["confirmed"],
            "waitlisted": snapshot["waitlisted"],
        }
        # Bulk reschedule the same accepted population; SQL-count comparisons use event queries.
        start = time.perf_counter()
        moved = await client.patch(
            f"/api/events/{identity}/schedule",
            headers=auth,
            json={
                "starts_at": (datetime.now(UTC) + timedelta(days=4)).isoformat(),
                "expected_schedule_version": snapshot["schedule_version"],
            },
        )
        moved.raise_for_status()
        result["reschedule_ms"] = round((time.perf_counter() - start) * 1000, 2)
        async with engine.connect() as connection:
            result["outbox"] = {
                str(status): int(count)
                for status, count in (
                    await connection.execute(
                        text(
                            "SELECT o.status, count(*) FROM email_outbox o JOIN registrations r "
                            "ON r.id=o.registration_id WHERE r.event_id=:id GROUP BY o.status"
                        ),
                        {"id": identity},
                    )
                ).all()
            }
            result["integrity"] = dict(
                zip(
                    ["duplicate_emails", "duplicate_queue_numbers"],
                    (
                        await connection.execute(
                            text(
                                "SELECT (SELECT count(*) FROM (SELECT 1 FROM registrations "
                                "GROUP BY event_id, email "
                                "HAVING count(*)>1) a), "
                                "(SELECT count(*) FROM (SELECT 1 FROM registrations "
                                "WHERE waitlist_seq IS NOT NULL GROUP BY event_id, waitlist_seq "
                                "HAVING count(*)>1) b)"
                            )
                        )
                    ).one(),
                    strict=True,
                )
            )
        assert result["integrity"] == {
            "duplicate_emails": 0,
            "duplicate_queue_numbers": 0,
        }
        # Isolate phases: do not reuse idle POST keep-alive sockets for long-lived streams.
        await client.aclose()
        live_client = httpx.AsyncClient(
            base_url="http://api:8000",
            timeout=30,
            limits=httpx.Limits(max_connections=visitors + 10),
        )
        connected = asyncio.Event()
        active, established, messages = 0, 0, 0
        stream_errors: dict[str, int] = {}
        observations: dict[int, tuple[int, float]] = {}

        async def visitor(index: int) -> None:
            nonlocal active, established, messages
            joined = False
            try:
                async with live_client.stream("GET", f"/api/events/{identity}/stream") as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.startswith("data:"):
                            validate_snapshot(line[5:].strip(), moved.json())
                            count = observations.get(index, (0, 0))[0]
                            observations[index] = (count + 1, time.perf_counter())
                            messages += 1
                            if not joined:
                                joined = True
                                active += 1
                                established += 1
                                if active == visitors:
                                    connected.set()
                    stream_errors["StreamClosed"] = stream_errors.get("StreamClosed", 0) + 1
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                name = type(exc).__name__
                stream_errors[name] = stream_errors.get(name, 0) + 1
            finally:
                if joined:
                    active -= 1

        tasks = [asyncio.create_task(visitor(index)) for index in range(visitors)]
        setup_ok = True
        try:
            await asyncio.wait_for(connected.wait(), 20)
        except TimeoutError:
            setup_ok = False
        try:
            await asyncio.sleep(1.2)
            before = await stats()
            await asyncio.sleep(8)
            after = await stats()
            result["sse"] = {
                "requested": visitors,
                "established": established,
                "active_before_close": active,
                "setup_within_20s": setup_ok,
                "errors": stream_errors.copy(),
                "messages": messages,
                "stale_clients": sum(
                    count < 2 or time.perf_counter() - last > 3
                    for count, last in (
                        observations.get(index, (0, 0)) for index in range(visitors)
                    )
                ),
                "db_commits_in_8_seconds": after[0] - before[0],
                "new_deadlocks": after[1] - before[1],
            }
        finally:
            for task in tasks:
                task.cancel()
            outcomes = await asyncio.gather(*tasks, return_exceptions=True)
            await live_client.aclose()
        unexpected = sum(
            isinstance(outcome, BaseException) and not isinstance(outcome, asyncio.CancelledError)
            for outcome in outcomes
        )
        result["sse"]["errors"] = stream_errors.copy()
        if unexpected:
            result["sse"]["errors"]["UnexpectedTaskFailure"] = unexpected
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    validate_result(result)


async def main() -> None:
    settings = Settings()
    engine = build_engine(settings)
    try:
        await probe(settings, engine)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
