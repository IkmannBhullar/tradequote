"""Fixed-window rate limiting, stored in Postgres.

"At most N requests per key per window": time is cut into fixed windows
(e.g. each clock minute) and each (key, window) gets a counter. Simple and
cheap. Its known weakness: a burst straddling a window boundary can briefly
reach 2N; a sliding window fixes that at the cost of more bookkeeping.
"""

import math
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.repositories.rate_limits import RateLimitRepository
from app.services.errors import RateLimitedError

# Counters older than this are useless; delete them as we go.
_KEEP_FOR = timedelta(days=1)


def _window_start(now: datetime, window: timedelta) -> datetime:
    seconds = int(window.total_seconds())
    return datetime.fromtimestamp(int(now.timestamp()) // seconds * seconds, tz=UTC)


def check(
    session: Session,
    *,
    key: str,
    limit: int,
    window: timedelta,
    now: datetime | None = None,
) -> None:
    """Count this request against `key`; raise RateLimitedError past `limit`.

    Commits immediately, so the request is counted even if the endpoint then
    fails (e.g. a wrong token): failed guesses must use up the budget too.
    """
    now = now or datetime.now(UTC)
    start = _window_start(now, window)
    repo = RateLimitRepository(session)
    count = repo.increment(key, start)
    repo.delete_windows_before(now - _KEEP_FOR)
    session.commit()

    if count > limit:
        retry_after = math.ceil((start + window - now).total_seconds())
        raise RateLimitedError(retry_after_seconds=max(retry_after, 1))
