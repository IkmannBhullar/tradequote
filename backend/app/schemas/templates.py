"""Trade template response shapes."""

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.enums import MeasureType


class TemplateItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    measure_type: MeasureType
    material_name: str
    material_unit: str
    material_unit_cost_cents: int
    coverage_per_material_unit: Decimal
    waste_factor: Decimal
    labor_hours_per_unit: Decimal
    default_coats: int


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    # None = a system default template.
    organization_id: uuid.UUID | None
    trade: str
    name: str
    items: list[TemplateItemOut]
