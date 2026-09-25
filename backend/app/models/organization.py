"""Organization: the tenant. Every contractor business is one organization."""

from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint("default_labor_rate_cents >= 0", name="labor_rate_non_negative"),
        # Stored as a fraction: 0.05 means 5%. Must be between 0% and 100%.
        CheckConstraint("tax_rate >= 0 AND tax_rate <= 1", name="tax_rate_range"),
    )

    name: Mapped[str] = mapped_column(String(200))
    logo_url: Mapped[str | None] = mapped_column(Text)
    # Money is always integer cents (BIGINT), never float (architecture rule 3).
    default_labor_rate_cents: Mapped[int] = mapped_column(BigInteger, server_default="0")
    # NUMERIC(6,5) is exact decimal math, read into Python as `Decimal`.
    # 5 decimal places allows rates like 0.04712 (4.712%).
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(6, 5), server_default="0")
