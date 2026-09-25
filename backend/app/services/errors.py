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
