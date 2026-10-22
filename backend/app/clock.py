from collections.abc import Callable
from datetime import UTC, datetime

type Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timezone-aware datetime required")
    try:
        return value.astimezone(UTC)
    except OverflowError as exc:
        raise ValueError("Datetime is outside the supported UTC range") from exc
