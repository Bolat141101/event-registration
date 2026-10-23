import json
from pathlib import Path

from notifications_app.contract import NotificationMessage as InboxMessage

from app.notifications.contract import NotificationMessage as CoreMessage


def test_both_services_match_the_versioned_contract() -> None:
    schema = json.loads(Path("/contract/v1.schema.json").read_text())
    assert CoreMessage.model_json_schema() == schema
    assert InboxMessage.model_json_schema() == schema
