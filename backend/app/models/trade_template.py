"""Trade templates: the data that makes the app trade-agnostic (rule 5).

A template (e.g. "Interior Painting") holds items (walls, ceilings, trim...),
and each item carries the numbers the estimating engine needs: material cost
and coverage, waste, and labor per unit. Adding a new trade means adding rows
here, never new code.
"""

import uuid
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, str_enum
from app.models.enums import MeasureType


class TradeTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "trade_templates"
    __table_args__ = (
        # No duplicate template names per org. NULLS NOT DISTINCT (Postgres 15+)
        # makes this apply to system templates too: by default SQL treats every
        # NULL as different, so two system "Interior Painting" rows would slip
        # through. This also makes the seed script's upsert safe.
        UniqueConstraint("organization_id", "trade", "name", postgresql_nulls_not_distinct=True),
    )

    # Not TenantMixin: NULL means a system default template that every
    # organization can copy. Non-NULL means the org's own template.
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    # Free text on purpose (e.g. "painting", "flooring"): trades are data.
    trade: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(200))

    # Deleting a template deletes its items: both in the ORM (cascade) and in
    # the database (ondelete=CASCADE on the FK). passive_deletes lets the
    # database do it instead of SQLAlchemy loading every item first.
    items: Mapped[list["TemplateItem"]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TemplateItem.name",
    )


class TemplateItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "template_items"
    __table_args__ = (
        UniqueConstraint("template_id", "name"),
        CheckConstraint("material_unit_cost_cents >= 0", name="material_cost_non_negative"),
        # Coverage is a divisor in the estimating formula, so 0 is forbidden.
        CheckConstraint("coverage_per_material_unit > 0", name="coverage_positive"),
        CheckConstraint("waste_factor >= 0", name="waste_non_negative"),
        CheckConstraint("labor_hours_per_unit >= 0", name="labor_non_negative"),
        CheckConstraint("default_coats >= 1", name="default_coats_positive"),
    )

    # The unique constraint above starts with template_id, so its index also
    # serves as the index for this foreign key.
    template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trade_templates.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(200))
    measure_type: Mapped[MeasureType] = mapped_column(str_enum(MeasureType, "measure_type"))
    material_name: Mapped[str] = mapped_column(String(200))
    material_unit: Mapped[str] = mapped_column(String(50))  # e.g. "gallon"
    material_unit_cost_cents: Mapped[int] = mapped_column(BigInteger)
    # How many measured units one material unit covers (e.g. 350 sq ft/gallon).
    coverage_per_material_unit: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    # Fraction of extra material to buy: 0.10 means +10%.
    waste_factor: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    # Per measured unit, per coat. Painting values are tiny (~0.006 h per
    # sq ft), hence 5 decimal places.
    labor_hours_per_unit: Mapped[Decimal] = mapped_column(Numeric(10, 5))
    default_coats: Mapped[int]

    template: Mapped[TradeTemplate] = relationship(back_populates="items")
