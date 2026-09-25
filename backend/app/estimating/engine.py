"""The estimating engine: pure functions from inputs to priced lines and totals.

Rules (CLAUDE.md, "Estimating rules"):
- Material units = quantity x coats x (1 + waste) / coverage, rounded UP to
  whole purchase units. Rounded per area (design choice: rooms are often
  different colors, so their paint can't be pooled).
- Labor hours = quantity x coats x labor_hours_per_unit, rounded to the
  nearest 0.25 h.
- Line totals in cents, rounded half-up. Tax = subtotal x rate, rounded
  half-up, applied once to the subtotal (not per line).
- Overrides replace a line's quantity and/or unit price and survive
  recalculation; the total is re-derived from them.
"""

import uuid
from decimal import Decimal, localcontext

from app.estimating.rounding import (
    round_half_up_to_cents,
    round_to_quarter_hour,
    round_up_to_whole_units,
)
from app.estimating.types import (
    AreaInput,
    Estimate,
    EstimatedLine,
    EstimateInput,
    LineKind,
    LineOverride,
)

LABOR_UNIT = "hour"

# Far more significant digits than any realistic quantity needs. Every
# multiplication below is then exact, and the one division is the only place
# rounding can happen (see _material_units).
_PRECISION = 50


def _material_units(area: AreaInput) -> int:
    rates = area.rates
    with localcontext(prec=_PRECISION):
        # Multiply first, divide once, last. With these inputs every product is
        # exact, so if the true answer is a whole number (e.g. exactly 3 cans),
        # the division yields exactly 3 and rounding up keeps it 3. Dividing
        # earlier could produce 2.99999...97 or 3.00000...01 and, with
        # round-UP, buy an extra can.
        needed = area.quantity * area.coats * (1 + rates.waste_factor)
        return round_up_to_whole_units(needed / rates.coverage_per_material_unit)


def _labor_hours(area: AreaInput) -> Decimal:
    with localcontext(prec=_PRECISION):
        return round_to_quarter_hour(area.quantity * area.coats * area.rates.labor_hours_per_unit)


def _line_total_cents(quantity: Decimal, unit_price_cents: int) -> int:
    with localcontext(prec=_PRECISION):
        return round_half_up_to_cents(quantity * unit_price_cents)


def estimate_area(area: AreaInput, labor_rate_cents: int) -> tuple[EstimatedLine, EstimatedLine]:
    """Calculate one area's (material, labor) lines, before any overrides."""
    units = _material_units(area)
    material = EstimatedLine(
        area_id=area.area_id,
        kind=LineKind.MATERIAL,
        description=f"{area.name}: {area.rates.material_name}",
        quantity=Decimal(units),
        unit=area.rates.material_unit,
        unit_price_cents=area.rates.material_unit_cost_cents,
        # Whole units x whole cents: exact integer math, nothing to round.
        total_cents=units * area.rates.material_unit_cost_cents,
        is_override=False,
    )

    hours = _labor_hours(area)
    labor = EstimatedLine(
        area_id=area.area_id,
        kind=LineKind.LABOR,
        description=f"{area.name}: labor",
        quantity=hours,
        unit=LABOR_UNIT,
        unit_price_cents=labor_rate_cents,
        # 0.25 h x an odd rate can produce a fraction of a cent.
        total_cents=_line_total_cents(hours, labor_rate_cents),
        is_override=False,
    )
    return material, labor


def _apply_override(line: EstimatedLine, override: LineOverride) -> EstimatedLine:
    """Return a copy of `line` with the override's values; the total is re-derived."""
    quantity = override.quantity if override.quantity is not None else line.quantity
    unit_price_cents = (
        override.unit_price_cents
        if override.unit_price_cents is not None
        else line.unit_price_cents
    )
    return EstimatedLine(
        area_id=line.area_id,
        kind=line.kind,
        description=line.description,
        quantity=quantity,
        unit=line.unit,
        unit_price_cents=unit_price_cents,
        total_cents=_line_total_cents(quantity, unit_price_cents),
        is_override=True,
    )


def calculate_estimate(estimate_input: EstimateInput) -> Estimate:
    """Price every area, apply overrides, and total the quote.

    Recalculating is just calling this again with the same overrides: they
    are re-applied to the fresh lines, which is how overrides "survive
    recalculation". An override whose area no longer exists is ignored.
    """
    overrides: dict[tuple[uuid.UUID, LineKind], LineOverride] = {
        override.line_key: override for override in estimate_input.overrides
    }

    lines: list[EstimatedLine] = []
    for area in estimate_input.areas:
        for line in estimate_area(area, estimate_input.labor_rate_cents):
            override = overrides.get((line.area_id, line.kind))
            lines.append(_apply_override(line, override) if override else line)

    subtotal_cents = sum(line.total_cents for line in lines)
    with localcontext(prec=_PRECISION):
        tax_cents = round_half_up_to_cents(subtotal_cents * estimate_input.tax_rate)

    return Estimate(
        lines=tuple(lines),
        subtotal_cents=subtotal_cents,
        tax_cents=tax_cents,
        total_cents=subtotal_cents + tax_cents,
    )
