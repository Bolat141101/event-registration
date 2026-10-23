from collections import Counter

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EmailOutbox, Registration
from tests.integration.business_support import Business
from tests.integration.test_api import client as client
from tests.integration.test_api_processes import APIClients, concurrent_posts
from tests.integration.test_api_processes import api_clients as api_clients

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


@pytest.mark.parametrize(
    "values",
    [
        ["User@faß.de", "user@xn--fa-hia.de", "USER@FAẞ.DE"],
        [" User@EXAMPLE.test ", "user@example.test"],
    ],
)
async def test_repeated_http_registration_is_one_identity(
    business: Business, client: AsyncClient, values: list[str]
) -> None:
    event = await business.create()
    for value in values:
        response = await client.post(f"/api/events/{event.id}/registrations", json={"email": value})
        assert response.status_code == 202 and set(response.json()) == {"message"}
    expected = "user@xn--fa-hia.de" if "faß" in values[0] else "user@example.test"
    async with AsyncSession(business.engine) as session:
        people = (
            await session.scalars(select(Registration).where(Registration.event_id == event.id))
        ).all()
        assert len(people) == 1 and people[0].email == expected and people[0].status == "confirmed"
        jobs = (
            await session.scalars(
                select(EmailOutbox).where(EmailOutbox.registration_id == people[0].id)
            )
        ).all()
        assert len(jobs) == 2 and all(job.payload["recipient"] == expected for job in jobs)
        assert Counter(job.kind.value for job in jobs) == {"ticket": 1, "reminder": 1}


async def test_idn_aliases_concurrently_across_two_api_processes(
    business: Business, api_clients: APIClients
) -> None:
    event = await business.create(capacity=1)
    responses = await concurrent_posts(
        business,
        api_clients,
        event.id,
        f"/api/events/{event.id}/registrations",
        ({"email": "USER@faß.de"}, {"email": "user@xn--fa-hia.de"}),
    )
    assert [response.status_code for response in responses] == [202, 202]
    assert responses[0].json() == responses[1].json()
    async with AsyncSession(business.engine) as session:
        entries = (
            await session.scalars(select(Registration).where(Registration.event_id == event.id))
        ).all()
        assert len(entries) == 1 and entries[0].email == "user@xn--fa-hia.de"
        assert entries[0].status == "confirmed" and entries[0].waitlist_seq is None
        jobs = (
            await session.scalars(
                select(EmailOutbox).where(EmailOutbox.registration_id == entries[0].id)
            )
        ).all()
        assert len(jobs) == 2
        assert all(job.payload["recipient"] == "user@xn--fa-hia.de" for job in jobs)


async def test_fass_is_distinct_dots_plus_and_other_events_are_preserved(
    business: Business,
) -> None:
    event = await business.create(capacity=5)
    inputs = [
        "user@faß.de",
        "user@fass.de",
        "some.one+tag@faß.de",
        "some.one@faß.de",
        "someone@faß.de",
    ]
    people = [await business.join(event.id, value) for value in inputs]
    assert len({person.id for person in people}) == 5
    other = await business.create()
    assert (await business.join(other.id, inputs[0])).id != people[0].id


async def test_raw_unicode_email_cannot_bypass_ascii_storage(business: Business) -> None:
    event = await business.create()
    person = await business.join(event.id, "user@faß.de")
    with pytest.raises(IntegrityError, match="normalized_email"):
        async with business.engine.begin() as connection:
            await connection.execute(
                text("UPDATE registrations SET email='user@faß.de' WHERE id=:id"), {"id": person.id}
            )
