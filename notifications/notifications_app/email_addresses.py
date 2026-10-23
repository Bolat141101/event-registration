"""Same identity policy as Core; compatibility is checked across services."""

from email_validator import EmailNotValidError, validate_email


def canonical_email(value: str) -> str:
    if any(character in value for character in "\r\n\x00"):
        raise ValueError("Invalid email address")
    try:
        result = validate_email(
            value.strip().lower(),
            check_deliverability=False,
            test_environment=True,
            allow_smtputf8=False,
        ).ascii_email
    except EmailNotValidError:
        raise ValueError("Invalid email address") from None
    if result is None:
        raise ValueError("ASCII email address required")
    return result.lower()
