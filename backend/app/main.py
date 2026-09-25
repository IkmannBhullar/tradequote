"""FastAPI application entry point.

Run locally with:  uv run uvicorn app.main:app --reload
"""

from fastapi import FastAPI

from app.api import health


def create_app() -> FastAPI:
    """Build and configure the app.

    An "application factory" (instead of only a module-level global) lets
    tests create a fresh, isolated app, and keeps all wiring in one place:
    every new router gets registered here.
    """
    app = FastAPI(title="TradeQuote API", version="0.1.0")
    app.include_router(health.router)
    return app


# The instance uvicorn serves (`app.main:app`).
app = create_app()
