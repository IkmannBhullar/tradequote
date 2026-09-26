"""Domain errors raised by services.

Services describe *what* went wrong in business terms; they never pick HTTP
status codes. One handler in app/api/errors.py maps each class to a status,
so every endpoint reports errors the same way and routers need no try/except.
"""


class DomainError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    """-> 404. Also used for other tenants' rows, so ids can't be probed."""

    def __init__(self, resource: str) -> None:
        super().__init__(f"{resource} not found")


class ConflictError(DomainError):
    """-> 409. The request is valid, but the current state doesn't allow it
    (e.g. editing an approved quote, deleting a client that has jobs)."""


class PermissionDeniedError(DomainError):
    """-> 403. Authenticated, but this role may not do this."""


class InvalidInputError(DomainError):
    """-> 422. Input that passes schema validation but breaks a business rule
    (e.g. a deposit larger than the quote total)."""


class GoneError(DomainError):
    """-> 410. It existed, but not anymore (e.g. an expired quote link)."""


class RateLimitedError(DomainError):
    """-> 429 with a Retry-After header."""

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("Too many requests. Please wait and try again.")
        self.retry_after_seconds = retry_after_seconds
