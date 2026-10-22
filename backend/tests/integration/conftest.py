from collections.abc import Iterator

import pytest
from sqlalchemy import Engine

from tests.integration.business_support import Business


@pytest.fixture
def business(integration_engine: Engine) -> Iterator[Business]:
    item = Business(integration_engine)
    try:
        yield item
    finally:
        item.cleanup()
