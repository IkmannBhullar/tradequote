"""App-wide HTTP error handling."""

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


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


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
