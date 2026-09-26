"""Atomic request counting for rate limits (not tenant-scoped: keyed by IP
or link, not by organization)."""

from datetime import datetime

from sqlalchemy import delete, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import RateLimitCounter


class RateLimitRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def increment(self, key: str, window_start: datetime) -> int:
        """Add one to the counter and return the new count, atomically.

        INSERT ... ON CONFLICT DO UPDATE is a single statement, so two
        simultaneous requests can't both read "59" and both write "60": the
        database serializes them and each gets its own number back.
        """
        statement = (
            insert(RateLimitCounter)
            .values(key=key, window_start=window_start, count=1)
            .on_conflict_do_update(
                constraint="uq_rate_limit_counters_key_window_start",
                set_={"count": RateLimitCounter.count + 1, "updated_at": func.now()},
            )
            .returning(RateLimitCounter.count)
        )
        return self._session.execute(statement).scalar_one()

    def delete_windows_before(self, cutoff: datetime) -> None:
        self._session.execute(
            delete(RateLimitCounter).where(RateLimitCounter.window_start < cutoff)
        )
