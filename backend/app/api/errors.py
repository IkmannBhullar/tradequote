"""App-wide HTTP error handling."""

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.services.errors import (
    ConflictError,
    DomainError,
    GoneError,
    InvalidInputError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitedError,
)

# Most specific first; checked in order.
_STATUS_BY_ERROR: list[tuple[type[DomainError], int]] = [
    (NotFoundError, status.HTTP_404_NOT_FOUND),
    (ConflictError, status.HTTP_409_CONFLICT),
    (PermissionDeniedError, status.HTTP_403_FORBIDDEN),
    (InvalidInputError, status.HTTP_422_UNPROCESSABLE_CONTENT),
    (GoneError, status.HTTP_410_GONE),
    (RateLimitedError, status.HTTP_429_TOO_MANY_REQUESTS),
]


async def _validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """422 responses, minus the `input` field.

    FastAPI's default 422 body echoes back the value that failed validation.
    For a too-short password, that means returning the password itself, which
    then lands in browser devtools, proxies, and error trackers. We keep the
    location, message, and constraints (e.g. min_length), and drop the input.
    """
    assert isinstance(exc, RequestValidationError)
    errors = [
        {key: value for key, value in error.items() if key != "input"} for error in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": jsonable_encoder(errors)},
    )


async def _domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Turn a service's DomainError into the matching HTTP status."""
    assert isinstance(exc, DomainError)
    status_code = next(code for cls, code in _STATUS_BY_ERROR if isinstance(exc, cls))
    headers = (
        # Standard header telling well-behaved clients how long to back off.
        {"Retry-After": str(exc.retry_after_seconds)} if isinstance(exc, RateLimitedError) else None
    )
    return JSONResponse(status_code=status_code, content={"detail": exc.message}, headers=headers)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    for error_class, _ in _STATUS_BY_ERROR:
        app.add_exception_handler(error_class, _domain_error_handler)
