"""Request counters for rate limiting the public (no-login) endpoints.

Stored in Postgres, not in process memory, so limits hold across any number
of API servers (12-factor: no local state). One row per (key, time window):
e.g. key "public-ip:203.0.113.7", window starting 14:05:00, count 37.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RateLimitCounter(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "rate_limit_counters"
    __table_args__ = (
        # The target of the atomic INSERT ... ON CONFLICT DO UPDATE upsert.
        UniqueConstraint("key", "window_start"),
        CheckConstraint("count >= 1", name="count_positive"),
    )

    key: Mapped[str] = mapped_column(String(200))
    # Indexed so old windows can be deleted cheaply.
    window_start: Mapped[datetime] = mapped_column(index=True)
    count: Mapped[int]
