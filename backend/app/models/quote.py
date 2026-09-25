"""Quote, its measured areas, and its priced line items.

- A Job can have several Quotes (versions 1, 2, 3...). Revising an approved
  quote creates a new version instead of editing it (rule 7).
- QuoteArea is what the contractor measured ("Living room walls, 420 sq ft").
- QuoteLineItem is the priced result. It's a *snapshot*: prices are copied in
  when calculated, so later template changes never alter an existing quote
  (rule 6).
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin, str_enum
from app.models.enums import MeasureType, QuoteStatus


class Quote(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "quotes"
    __table_args__ = (
        # Tenant safety net: a quote's job must belong to the same org.
        ForeignKeyConstraint(
            ["organization_id", "job_id"],
            ["jobs.organization_id", "jobs.id"],
            ondelete="RESTRICT",
        ),
        # One version 1, one version 2... per job. Its index (job_id first)
        # also serves lookups of a job's quotes.
        UniqueConstraint("job_id", "version"),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint(
            "subtotal_cents >= 0 AND tax_cents >= 0 AND deposit_required_cents >= 0",
            name="amounts_non_negative",
        ),
        # Catches rounding/arithmetic bugs at the database level.
        CheckConstraint("total_cents = subtotal_cents + tax_cents", name="total_is_sum"),
        CheckConstraint("deposit_required_cents <= total_cents", name="deposit_within_total"),
        # A token without an expiry (or vice versa) would be a bug.
        CheckConstraint(
            "(public_token_hash IS NULL) = (token_expires_at IS NULL)",
            name="token_hash_and_expiry_together",
        ),
        # An approved quote must record when and by whom.
        CheckConstraint(
            "status <> 'approved' OR (approved_at IS NOT NULL AND approved_by_name IS NOT NULL)",
            name="approval_recorded",
        ),
    )

    job_id: Mapped[uuid.UUID]
    version: Mapped[int]
    status: Mapped[QuoteStatus] = mapped_column(
        str_enum(QuoteStatus, "quote_status"), server_default=QuoteStatus.DRAFT.value
    )
    # SHA-256 hex digest (always 64 chars) of the public approval token. The
    # raw token is only ever in the link we send; a leaked database can't be
    # turned back into working links (rule 8).
    public_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    token_expires_at: Mapped[datetime | None]
    subtotal_cents: Mapped[int] = mapped_column(BigInteger, server_default="0")
    tax_cents: Mapped[int] = mapped_column(BigInteger, server_default="0")
    total_cents: Mapped[int] = mapped_column(BigInteger, server_default="0")
    deposit_required_cents: Mapped[int] = mapped_column(BigInteger, server_default="0")
    approved_at: Mapped[datetime | None]
    approved_by_name: Mapped[str | None] = mapped_column(String(200))

    areas: Mapped[list["QuoteArea"]] = relationship(
        back_populates="quote", cascade="all, delete-orphan", passive_deletes=True
    )
    line_items: Mapped[list["QuoteLineItem"]] = relationship(
        back_populates="quote", cascade="all, delete-orphan", passive_deletes=True
    )


class QuoteArea(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "quote_areas"
    __table_args__ = (
        # Lets line items use a composite FK (quote_id, area_id) so a line item
        # can only reference an area on the *same* quote.
        UniqueConstraint("quote_id", "id"),
        CheckConstraint("quantity >= 0", name="quantity_non_negative"),
        CheckConstraint("coats >= 1", name="coats_positive"),
    )

    # No organization_id here: areas are only ever reached through their quote,
    # which is tenant-filtered. The unique constraint above indexes quote_id.
    quote_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quotes.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    measure_type: Mapped[MeasureType] = mapped_column(str_enum(MeasureType, "measure_type"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    # SET NULL: deleting a template item must not delete or break quotes; the
    # prices already live in quote_line_items. (The service layer must check
    # the item belongs to the quote's org or is a system item. A DB constraint
    # can't express "same org OR NULL org" simply.)
    template_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("template_items.id", ondelete="SET NULL"), index=True
    )
    coats: Mapped[int]

    quote: Mapped[Quote] = relationship(back_populates="areas")


class QuoteLineItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "quote_line_items"
    __table_args__ = (
        # If area_id is set, the area must be on this same quote. (With a NULL
        # area_id, Postgres skips the check, which is what we want for
        # quote-level lines.) Deleting an area deletes its line items.
        ForeignKeyConstraint(
            ["quote_id", "area_id"],
            ["quote_areas.quote_id", "quote_areas.id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("quantity >= 0", name="quantity_non_negative"),
        CheckConstraint("unit_price_cents >= 0 AND total_cents >= 0", name="amounts_non_negative"),
    )

    quote_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quotes.id", ondelete="CASCADE"), index=True
    )
    # NULL for lines that belong to the whole quote rather than one area.
    area_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    description: Mapped[str] = mapped_column(Text)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    unit: Mapped[str] = mapped_column(String(50))
    unit_price_cents: Mapped[int] = mapped_column(BigInteger)
    total_cents: Mapped[int] = mapped_column(BigInteger)
    # True when the contractor edited this line by hand; recalculation must
    # keep it as-is.
    is_override: Mapped[bool] = mapped_column(server_default="false")

    quote: Mapped[Quote] = relationship(back_populates="line_items")
