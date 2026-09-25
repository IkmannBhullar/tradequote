"""Shared schema pieces: pagination envelope, reusable field types."""

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

# Reusable constrained types, so the same rules apply on every endpoint.
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=50)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
Cents = Annotated[int, Field(ge=0, le=10**13)]  # up to $100 billion: plenty
# Match the database columns exactly, so nothing gets silently rounded.
Quantity = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=3)]
TaxRate = Annotated[Decimal, Field(ge=0, le=1, max_digits=6, decimal_places=5)]


class Page[T](BaseModel):
    """One page of a list, plus what the client needs to page through it."""

    items: list[T]
    total: int
    limit: int
    offset: int


def reject_explicit_nulls(model: BaseModel, fields: tuple[str, ...]) -> None:
    """PATCH bodies: omitting a field means "leave it alone", but sending
    null for a required field (e.g. a client's name) is an error. Without
    this check, the null would reach the database as a NOT NULL violation.
    """
    for field in fields:
        if field in model.model_fields_set and getattr(model, field) is None:
            raise ValueError(f"{field} can't be null")
