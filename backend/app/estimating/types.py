"""Inputs and outputs of the estimating engine.

Plain frozen dataclasses: not ORM models, not Pydantic schemas. The engine
depends on nothing but the standard library, so it can't accidentally touch
the database or the network, and it's trivial to test.

Each input validates itself in __post_init__, so an invalid input can't be
constructed at all ("make invalid states unrepresentable"). The database has
the same rules, but the engine doesn't trust its callers.
"""

import enum
import uuid
from dataclasses import dataclass
from decimal import Decimal

# quote_line_items.quantity is NUMERIC(12, 3). Postgres would silently round
# a 4th decimal place, breaking total == quantity x unit price, so we refuse
# such quantities up front.
LINE_QUANTITY_PLACES = 3


def _require_finite_non_negative(name: str, value: Decimal) -> None:
    # Decimal can hold NaN and Infinity; neither is a valid measurement.
    if not value.is_finite() or value < 0:
        raise ValueError(f"{name} must be a finite number >= 0, got {value}")


def _require_non_negative_int(name: str, value: int) -> None:
    if value < 0:
        raise ValueError(f"{name} must be >= 0, got {value}")


class LineKind(enum.StrEnum):
    """Every area produces exactly one line of each kind."""

    MATERIAL = "material"
    LABOR = "labor"


@dataclass(frozen=True)
class ItemRates:
    """The numbers from a template item that the math needs.

    Deliberately no trade, no measure_type: the formulas are identical for
    square feet, linear feet, or door counts. That's what keeps trades as data.
    """

    material_name: str
    material_unit: str  # e.g. "gallon"
    material_unit_cost_cents: int
    coverage_per_material_unit: Decimal  # measured units covered by one material unit
    waste_factor: Decimal  # 0.10 = buy 10% extra
    labor_hours_per_unit: Decimal  # per measured unit, per coat

    def __post_init__(self) -> None:
        _require_non_negative_int("material_unit_cost_cents", self.material_unit_cost_cents)
        _require_finite_non_negative("waste_factor", self.waste_factor)
        _require_finite_non_negative("labor_hours_per_unit", self.labor_hours_per_unit)
        _require_finite_non_negative("coverage_per_material_unit", self.coverage_per_material_unit)
        # Coverage is the divisor in the material formula.
        if self.coverage_per_material_unit == 0:
            raise ValueError("coverage_per_material_unit must be > 0")


@dataclass(frozen=True)
class AreaInput:
    """One measured area, e.g. 'Living room walls: 420 sq ft, 2 coats'."""

    area_id: uuid.UUID  # identifies the area's lines, so overrides can find them
    name: str
    quantity: Decimal
    coats: int
    rates: ItemRates

    def __post_init__(self) -> None:
        _require_finite_non_negative("quantity", self.quantity)
        if self.coats < 1:
            raise ValueError(f"coats must be >= 1, got {self.coats}")


@dataclass(frozen=True)
class LineOverride:
    """A contractor's manual change to one calculated line.

    Replaces the quantity and/or the unit price; the line total is always
    derived (quantity x unit price), so quotes stay arithmetically consistent.
    """

    area_id: uuid.UUID
    kind: LineKind
    quantity: Decimal | None = None
    unit_price_cents: int | None = None

    def __post_init__(self) -> None:
        if self.quantity is None and self.unit_price_cents is None:
            raise ValueError("an override must set quantity, unit_price_cents, or both")
        if self.quantity is not None:
            _require_finite_non_negative("override quantity", self.quantity)
            if self.quantity != round(self.quantity, LINE_QUANTITY_PLACES):
                raise ValueError(
                    f"override quantity may have at most {LINE_QUANTITY_PLACES} decimal "
                    f"places, got {self.quantity}"
                )
        if self.unit_price_cents is not None:
            _require_non_negative_int("override unit_price_cents", self.unit_price_cents)

    @property
    def line_key(self) -> tuple[uuid.UUID, LineKind]:
        return (self.area_id, self.kind)


@dataclass(frozen=True)
class EstimateInput:
    areas: tuple[AreaInput, ...]
    labor_rate_cents: int  # per hour
    tax_rate: Decimal  # 0.05 = 5%
    # Tuples, not lists: frozen dataclasses should hold immutable collections.
    overrides: tuple[LineOverride, ...] = ()

    def __post_init__(self) -> None:
        _require_non_negative_int("labor_rate_cents", self.labor_rate_cents)
        _require_finite_non_negative("tax_rate", self.tax_rate)
        if self.tax_rate > 1:
            raise ValueError(f"tax_rate must be a fraction between 0 and 1, got {self.tax_rate}")

        area_ids = [area.area_id for area in self.areas]
        if len(area_ids) != len(set(area_ids)):
            raise ValueError("area_id values must be unique")

        line_keys = [override.line_key for override in self.overrides]
        if len(line_keys) != len(set(line_keys)):
            raise ValueError("at most one override per (area_id, kind)")


@dataclass(frozen=True)
class EstimatedLine:
    """One priced line: what becomes a quote_line_items row."""

    area_id: uuid.UUID
    kind: LineKind
    description: str
    quantity: Decimal
    unit: str
    unit_price_cents: int
    total_cents: int
    is_override: bool


@dataclass(frozen=True)
class Estimate:
    lines: tuple[EstimatedLine, ...]
    subtotal_cents: int
    tax_cents: int
    total_cents: int
