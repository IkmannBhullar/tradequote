"""Fixed-window rate limiter (services/rate_limit.py)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import RateLimitCounter
from app.services import rate_limit
from app.services.errors import RateLimitedError

MINUTE = timedelta(minutes=1)
T0 = datetime(2026, 9, 25, 14, 5, 0, tzinfo=UTC)  # exactly at a window start


def hit(session: Session, now: datetime, key: str = "k", limit: int = 3) -> None:
    rate_limit.check(session, key=key, limit=limit, window=MINUTE, now=now)


def test_allows_up_to_the_limit_then_blocks(db_session: Session) -> None:
    for second in range(3):
        hit(db_session, T0 + timedelta(seconds=second))

    with pytest.raises(RateLimitedError) as blocked:
        hit(db_session, T0 + timedelta(seconds=20))

    # Retry-After: seconds until the next window starts.
    assert blocked.value.retry_after_seconds == 40


def test_a_new_window_starts_fresh(db_session: Session) -> None:
    for _ in range(3):
        hit(db_session, T0)
    hit(db_session, T0 + MINUTE)  # no error: new window


def test_keys_are_independent(db_session: Session) -> None:
    for _ in range(3):
        hit(db_session, T0, key="a")
    hit(db_session, T0, key="b")  # no error


def test_old_windows_are_cleaned_up(db_session: Session) -> None:
    hit(db_session, T0, key="old")
    hit(db_session, T0 + timedelta(days=2), key="new")

    keys = db_session.scalars(select(RateLimitCounter.key)).all()
    assert keys == ["new"]
    assert db_session.scalar(select(func.count()).select_from(RateLimitCounter)) == 1
