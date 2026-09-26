"""Quote, its measured areas, and its priced line items.

- A Job can have several Quotes (versions 1, 2, 3...). Revising a sent or
  approved quote creates a new version instead of editing it (rule 7).
- QuoteArea is what the contractor measured ("Living room walls, 420 sq ft").
- QuoteLineItem is the priced result (one material + one labor line per area).

Price snapshots (rule 6): a quote carries copies of every rate it uses. The
labor/tax rates are copied onto the quote when it's created, and each area
copies its template item's rates when it's added. Recalculation reads only
these copies, so editing or deleting a template later can never change an
existing quote.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:  # imported only for type checking, avoiding a circular import
    from app.models.job import Job

from app.models.base import (
    Base,
    TenantScopedModel,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    str_enum,
)
from app.models.enums import LineItemKind, MeasureType, QuoteStatus


class Quote(TenantScopedModel):
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
        # (M6) A declined quote must record when and by whom.
        CheckConstraint(
            "status <> 'declined' OR (declined_at IS NOT NULL AND declined_by_name IS NOT NULL)",
            name="decline_recorded",
        ),
        # (M6) Anything past draft has been sent.
        CheckConstraint("status = 'draft' OR sent_at IS NOT NULL", name="sent_recorded"),
        CheckConstraint("labor_rate_cents >= 0", name="labor_rate_non_negative"),
        CheckConstraint("tax_rate >= 0 AND tax_rate <= 1", name="tax_rate_range"),
    )

    job_id: Mapped[uuid.UUID]
    version: Mapped[int]
    status: Mapped[QuoteStatus] = mapped_column(
        str_enum(QuoteStatus, "quote_status"), server_default=QuoteStatus.DRAFT.value
    )
    # (M4) Snapshots of the organization's rates when this quote was created.
    labor_rate_cents: Mapped[int] = mapped_column(BigInteger)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(6, 5))
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
    # (M6) Sending and declining.
    sent_at: Mapped[datetime | None]
    declined_at: Mapped[datetime | None]
    declined_by_name: Mapped[str | None] = mapped_column(String(200))
    decline_reason: Mapped[str | None] = mapped_column(Text)

    # (M6) Read-only link to the job (for PDFs and the public page). viewonly:
    # the composite foreign key already manages job_id and organization_id.
    job: Mapped["Job"] = relationship(primaryjoin="foreign(Quote.job_id) == Job.id", viewonly=True)
    areas: Mapped[list["QuoteArea"]] = relationship(
        back_populates="quote",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="QuoteArea.position",
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
        # (M4) Same rules as the template_items these values are copied from.
        CheckConstraint("material_unit_cost_cents >= 0", name="material_cost_non_negative"),
        CheckConstraint("coverage_per_material_unit > 0", name="coverage_positive"),
        CheckConstraint("waste_factor >= 0", name="waste_non_negative"),
        CheckConstraint("labor_hours_per_unit >= 0", name="labor_non_negative"),
        CheckConstraint("position >= 0", name="position_non_negative"),
    )

    # No organization_id here: areas are only ever reached through their quote,
    # which is tenant-filtered. The unique constraint above indexes quote_id.
    quote_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quotes.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    measure_type: Mapped[MeasureType] = mapped_column(str_enum(MeasureType, "measure_type"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    # Where the rates below were copied from. SET NULL: deleting a template
    # item must not delete or break quotes (the snapshot has what we need).
    template_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("template_items.id", ondelete="SET NULL"), index=True
    )
    coats: Mapped[int]
    # (M4) Display order within the quote. Explicit, because created_at can't
    # order rows inserted in the same transaction: Postgres's now() is the
    # transaction's start time, so they'd all tie.
    position: Mapped[int]

    # (M4) Snapshot of the template item's rates when the area was added.
    material_name: Mapped[str] = mapped_column(String(200))
    material_unit: Mapped[str] = mapped_column(String(50))
    material_unit_cost_cents: Mapped[int] = mapped_column(BigInteger)
    coverage_per_material_unit: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    waste_factor: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    labor_hours_per_unit: Mapped[Decimal] = mapped_column(Numeric(10, 5))

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
        # (M4) Each area has exactly one material and one labor line. This is
        # the line's stable identity, which overrides attach to.
        UniqueConstraint("area_id", "kind"),
        CheckConstraint(
            "(override_quantity IS NULL OR override_quantity >= 0)"
            " AND (override_unit_price_cents IS NULL OR override_unit_price_cents >= 0)",
            name="override_values_non_negative",
        ),
        # The flag can't disagree with the stored override values.
        CheckConstraint(
            "is_override = "
            "(override_quantity IS NOT NULL OR override_unit_price_cents IS NOT NULL)",
            name="override_flag_consistent",
        ),
    )

    quote_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quotes.id", ondelete="CASCADE"), index=True
    )
    # NULL for lines that belong to the whole quote rather than one area.
    area_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    kind: Mapped[LineItemKind] = mapped_column(str_enum(LineItemKind, "line_item_kind"))
    description: Mapped[str] = mapped_column(Text)
    # The values actually used (calculated, or the override where one is set).
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    unit: Mapped[str] = mapped_column(String(50))
    unit_price_cents: Mapped[int] = mapped_column(BigInteger)
    total_cents: Mapped[int] = mapped_column(BigInteger)
    # (M4) What the contractor overrode, stored separately from the result so
    # recalculation knows exactly which parts to keep. E.g. a price-only
    # override keeps following re-measured quantities.
    override_quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    override_unit_price_cents: Mapped[int | None] = mapped_column(BigInteger)
    # True when either override value is set (enforced by a CHECK above).
    is_override: Mapped[bool] = mapped_column(server_default="false")

    quote: Mapped[Quote] = relationship(back_populates="line_items")
