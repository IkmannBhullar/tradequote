"""Quote, area, and override request/response shapes."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import Quote
from app.models.enums import LineItemKind, MeasureType, QuoteStatus
from app.schemas.common import Cents, Name, Quantity, reject_explicit_nulls

Coats = Annotated[int, Field(ge=1, le=20)]


class QuoteUpdate(BaseModel):
    deposit_required_cents: Cents


class AreaCreate(BaseModel):
    template_item_id: uuid.UUID
    name: Name
    quantity: Quantity
    coats: Coats | None = None  # defaults to the template item's default_coats


class AreaUpdate(BaseModel):
    name: Name | None = None
    quantity: Quantity | None = None
    coats: Coats | None = None

    @model_validator(mode="after")
    def _required_not_null(self) -> Self:
        reject_explicit_nulls(self, ("name", "quantity", "coats"))
        return self


class OverrideRequest(BaseModel):
    """Replace a line's quantity and/or unit price. The total is derived."""

    quantity: Quantity | None = None
    unit_price_cents: Cents | None = None

    @model_validator(mode="after")
    def _at_least_one(self) -> Self:
        if self.quantity is None and self.unit_price_cents is None:
            raise ValueError("set quantity, unit_price_cents, or both")
        return self


class AreaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    position: int
    name: str
    measure_type: MeasureType
    quantity: Decimal
    coats: int
    template_item_id: uuid.UUID | None
    # The rate snapshot this area is priced with.
    material_name: str
    material_unit: str
    material_unit_cost_cents: int
    coverage_per_material_unit: Decimal
    waste_factor: Decimal
    labor_hours_per_unit: Decimal


class LineItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    area_id: uuid.UUID | None
    kind: LineItemKind
    description: str
    quantity: Decimal
    unit: str
    unit_price_cents: int
    total_cents: int
    is_override: bool
    override_quantity: Decimal | None
    override_unit_price_cents: int | None


class QuoteSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    version: int
    status: QuoteStatus
    subtotal_cents: int
    tax_cents: int
    total_cents: int
    deposit_required_cents: int
    created_at: datetime


class QuoteOut(QuoteSummaryOut):
    labor_rate_cents: int
    tax_rate: Decimal
    approved_at: datetime | None
    approved_by_name: str | None
    areas: list[AreaOut]
    line_items: list[LineItemOut]

    @classmethod
    def from_quote(cls, quote: Quote) -> "QuoteOut":
        """Build the response with line items in a stable, readable order:
        by area (in the order areas were added), material before labor."""
        area_position = {area.id: index for index, area in enumerate(quote.areas)}
        kind_position = {LineItemKind.MATERIAL: 0, LineItemKind.LABOR: 1}
        out = cls.model_validate(quote, from_attributes=True)
        out.line_items.sort(
            key=lambda line: (
                area_position.get(line.area_id, len(area_position)) if line.area_id else 0,
                kind_position[line.kind],
            )
        )
        return out
