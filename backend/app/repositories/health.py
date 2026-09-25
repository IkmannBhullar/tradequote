"""Database access for health checks."""

from sqlalchemy import text
from sqlalchemy.orm import Session


def ping(session: Session) -> None:
    """Run the cheapest possible query to prove the database answers.

    Raises a SQLAlchemy error if the database is unreachable. Deciding what
    that *means* is the service layer's job, not this one's.
    """
    session.execute(text("SELECT 1"))
