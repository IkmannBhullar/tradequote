"""Health-check logic: turns low-level DB errors into a simple yes/no."""

import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.repositories import health as health_repository

logger = logging.getLogger(__name__)


def is_database_ready(session: Session) -> bool:
    """Return True if the database responds to a trivial query."""
    try:
        health_repository.ping(session)
    except SQLAlchemyError:
        # Log the real error for operators, but don't leak connection details
        # (hostnames, usernames) through a public HTTP response.
        logger.exception("Database readiness check failed")
        return False
    return True
