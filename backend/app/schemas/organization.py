"""Organization settings update."""

from typing import Self

from pydantic import BaseModel, HttpUrl, model_validator

from app.schemas.common import Cents, Name, TaxRate, reject_explicit_nulls


class OrganizationUpdate(BaseModel):
    name: Name | None = None
    logo_url: HttpUrl | None = None  # send null to remove the logo
    default_labor_rate_cents: Cents | None = None  # per hour
    tax_rate: TaxRate | None = None  # 0.05 = 5%

    @model_validator(mode="after")
    def _required_not_null(self) -> Self:
        reject_explicit_nulls(self, ("name", "default_labor_rate_cents", "tax_rate"))
        return self
