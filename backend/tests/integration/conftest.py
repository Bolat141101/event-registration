from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.integration.business_support import Business


@pytest.fixture
async def business(integration_engine: AsyncEngine) -> AsyncIterator[Business]:
    item = Business(integration_engine)
    try:
        yield item
    finally:
        await item.cleanup()
