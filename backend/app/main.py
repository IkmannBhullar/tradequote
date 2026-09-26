"""FastAPI application entry point.

Run locally with:  uv run uvicorn app.main:app --reload
"""

from fastapi import FastAPI

from app.api import (
    auth,
    clients,
    health,
    jobs,
    me,
    organization,
    payments,
    public,
    quotes,
    templates,
)
from app.api.errors import register_error_handlers


def create_app() -> FastAPI:
    """Build and configure the app.

    An "application factory" (instead of only a module-level global) lets
    tests create a fresh, isolated app, and keeps all wiring in one place:
    every new router gets registered here.
    """
    app = FastAPI(title="TradeQuote API", version="0.1.0")
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(me.router)
    app.include_router(organization.router)
    app.include_router(templates.router)
    app.include_router(clients.router)
    app.include_router(jobs.router)
    app.include_router(quotes.router)
    app.include_router(payments.router)
    app.include_router(public.router)
    return app


# The instance uvicorn serves (`app.main:app`).
app = create_app()
