import json
from pathlib import Path

import pytest
from notifications_app.contract import NotificationMessage as InboxMessage
from notifications_app.email_addresses import canonical_email as notification_email

from app.email_addresses import canonical_email as core_email
from app.notifications.contract import NotificationMessage as CoreMessage


def test_both_services_match_the_versioned_contract() -> None:
    schema = json.loads(Path("/contract/v1.schema.json").read_text())
    assert CoreMessage.model_json_schema() == schema
    assert InboxMessage.model_json_schema() == schema


@pytest.mark.parametrize(
    "value,expected",
    [
        ("user@faß.de", "user@xn--fa-hia.de"),
        ("user@xn--fa-hia.de", "user@xn--fa-hia.de"),
        (" USER@FAẞ.DE ", "user@xn--fa-hia.de"),
        ("user@fass.de", "user@fass.de"),
        ("Some.One+Tag@Example.test", "some.one+tag@example.test"),
        ("user@пример.рф", "user@xn--e1afmkfd.xn--p1ai"),
    ],
)
def test_canonical_email_policy_is_identical_across_services(value: str, expected: str) -> None:
    assert core_email(value) == notification_email(value) == expected
