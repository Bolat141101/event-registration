"""Real edge limits. Run a disposable low-budget proxy and the normal frontend."""

import asyncio
import os
from contextlib import AsyncExitStack
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx

from app.config import Settings


async def main() -> None:
    project = os.environ["LOAD_PROJECT"]
    if not project.startswith("event-registration-relay-check-ui-"):
        raise SystemExit("Isolated project required")
    proxy = "http://" + project + "-limits"
    auth = {"Authorization": "Bearer " + Settings().organizer_token.get_secret_value()}
    async with httpx.AsyncClient(timeout=10, limits=httpx.Limits(max_connections=40)) as client:
        response = await client.post(
            "http://api:8000/api/events",
            headers=auth,
            json={
                "description": "Edge admission probe",
                "capacity": 30,
                "starts_at": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
            },
        )
        response.raise_for_status()
        identity = response.json()["id"]
        path = f"/api/events/{identity}/registrations"
        # Invalid input makes the probe cheap; spoofed XFF must not reset the IP bucket.
        for _ in range(3):
            assert (await client.post(proxy + path, json={"email": ""})).status_code == 422
        rejected = await client.post(
            proxy + path, headers={"X-Forwarded-For": "192.0.2.42"}, json={"email": ""}
        )
        assert rejected.status_code == 429 and rejected.json()["code"] == "rate_limited"
        assert rejected.headers["retry-after"] == "2"
        assert rejected.json()["message"] == "Please wait a moment and try again"
        async with AsyncExitStack() as stack:
            for _ in range(2):
                stream = await stack.enter_async_context(
                    client.stream("GET", proxy + f"/api/events/{identity}/stream")
                )
                assert stream.status_code == 200
            rejected = await client.get(proxy + f"/api/events/{identity}/stream")
            assert rejected.status_code == 429
            assert (await client.get(proxy + "/api/health")).status_code == 200
        # All these legitimate clients share a single NAT at the normal edge.
        tag = uuid4().hex[:10]
        responses = await asyncio.gather(
            *(
                client.post("http://frontend" + path, json={"email": f"nat+{tag}-{i}@example.test"})
                for i in range(20)
            )
        )
        assert all(item.status_code == 202 for item in responses)
        async with AsyncExitStack() as stack:
            for _ in range(20):
                stream = await stack.enter_async_context(
                    client.stream("GET", f"http://frontend/api/events/{identity}/stream")
                )
                assert stream.status_code == 200
    print(
        "Edge: rate/connection limits, Retry-After, spoofed XFF, "
        "health independence and 20 shared-NAT clients PASS"
    )


if __name__ == "__main__":
    asyncio.run(main())
