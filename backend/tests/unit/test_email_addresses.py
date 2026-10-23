import pytest

from app.email_addresses import canonical_email
from app.services.common import normalize_email
from app.services.errors import InvalidInput


@pytest.mark.parametrize(
    "value,expected",
    [
        ("user@faß.de", "user@xn--fa-hia.de"),
        ("user@xn--fa-hia.de", "user@xn--fa-hia.de"),
        (" USER@FAẞ.DE ", "user@xn--fa-hia.de"),
        ("Some.One+Tag@EXAMPLE.test", "some.one+tag@example.test"),
        ("user@fass.de", "user@fass.de"),
        ("user@пример.рф", "user@xn--e1afmkfd.xn--p1ai"),
    ],
)
def test_ascii_canonical_identity(value: str, expected: str) -> None:
    assert canonical_email(value) == normalize_email(value) == expected
    assert canonical_email(expected) == expected


@pytest.mark.parametrize(
    "value", ["тест@example.test", "user@example.test\r\n", "Name <user@example.test>"]
)
def test_reject_smtputf8_and_unsafe_input(value: str) -> None:
    with pytest.raises(ValueError):
        canonical_email(value)
    with pytest.raises(InvalidInput):
        normalize_email(value)
