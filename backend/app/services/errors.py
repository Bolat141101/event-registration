class DomainError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class NotFound(DomainError):
    pass


class Conflict(DomainError):
    pass


class Unauthorized(DomainError):
    pass


class InvalidInput(DomainError):
    pass
