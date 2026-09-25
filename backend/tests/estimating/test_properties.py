"""Property-based tests: rules that must hold for EVERY valid input.

Instead of hand-picking examples, we describe what valid input looks like
(the "strategies" below) and Hypothesis generates hundreds of cases per test,
hunting for a counterexample. When it finds one, it shrinks it to the
simplest failing input and reports that.
"""

from decimal import Decimal, localcontext

from hypothesis import given, settings
from hypothesis import strategies as st

from app.estimating import (
    AreaInput,
    Estimate,
    EstimateInput,
    ItemRates,
    LineKind,
    LineOverride,
    calculate_estimate,
)
from app.estimating.rounding import round_half_up_to_cents

# deadline=None: no per-example time limit, so a slow CI machine can't cause
# flaky failures. More examples than the default 100 since the engine is fast.
PROPERTY_SETTINGS = settings(max_examples=300, deadline=None)

# Plenty of digits for the exact reference math inside the assertions.
EXACT = 60

# ---------------------------------------------------------------------------
# Strategies: generators of valid inputs, mirroring the database's limits
# ---------------------------------------------------------------------------


def decimals(min_value: str, max_value: str, places: int) -> st.SearchStrategy[Decimal]:
    return st.decimals(
        min_value=Decimal(min_value),
        max_value=Decimal(max_value),
        places=places,
        allow_nan=False,
        allow_infinity=False,
    )


item_rates = st.builds(
    ItemRates,
    material_name=st.just("Paint"),
    material_unit=st.just("gallon"),
    material_unit_cost_cents=st.integers(0, 100_000),
    coverage_per_material_unit=decimals("0.001", "10000", 3),  # NUMERIC(10,3), > 0
    waste_factor=decimals("0", "1", 4),  # NUMERIC(5,4)
    labor_hours_per_unit=decimals("0", "10", 5),  # NUMERIC(10,5)
)

areas = st.builds(
    AreaInput,
    area_id=st.uuids(),
    name=st.just("Area"),
    quantity=decimals("0", "1000000", 3),  # NUMERIC(12,3)
    coats=st.integers(1, 5),
    rates=item_rates,
)

area_lists = st.lists(areas, max_size=6, unique_by=lambda area: area.area_id)
labor_rates = st.integers(0, 50_000)
tax_rates = decimals("0", "1", 5)  # NUMERIC(6,5)


@st.composite
def estimate_inputs(draw: st.DrawFn) -> EstimateInput:
    """An estimate input whose overrides target (some of) its own areas' lines."""
    drawn_areas = tuple(draw(area_lists))
    overrides: list[LineOverride] = []
    for area in drawn_areas:
        for kind in LineKind:
            if not draw(st.booleans()):
                continue
            quantity = draw(st.none() | decimals("0", "100000", 3))
            # An override must set at least one of the two fields.
            price_strategy = (
                st.integers(0, 100_000) if quantity is None else st.none() | st.integers(0, 100_000)
            )
            overrides.append(
                LineOverride(
                    area.area_id, kind, quantity=quantity, unit_price_cents=draw(price_strategy)
                )
            )
    return EstimateInput(
        areas=drawn_areas,
        labor_rate_cents=draw(labor_rates),
        tax_rate=draw(tax_rates),
        overrides=tuple(overrides),
    )


def _without_overrides(estimate_input: EstimateInput) -> Estimate:
    return calculate_estimate(
        EstimateInput(
            areas=estimate_input.areas,
            labor_rate_cents=estimate_input.labor_rate_cents,
            tax_rate=estimate_input.tax_rate,
        )
    )


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


@PROPERTY_SETTINGS
@given(area=areas, labor_rate_cents=labor_rates)
def test_material_always_covers_the_need_without_a_spare_unit(
    area: AreaInput, labor_rate_cents: int
) -> None:
    result = calculate_estimate(
        EstimateInput(areas=(area,), labor_rate_cents=labor_rate_cents, tax_rate=Decimal("0"))
    )
    units = result.lines[0].quantity

    with localcontext(prec=EXACT):
        coverage = area.rates.coverage_per_material_unit
        need = area.quantity * area.coats * (1 + area.rates.waste_factor)
        assert units == units.to_integral_value()  # whole purchase units
        assert units * coverage >= need  # enough to finish the job
        if units > 0:
            assert (units - 1) * coverage < need  # ...and not a whole unit extra


@PROPERTY_SETTINGS
@given(area=areas, labor_rate_cents=labor_rates)
def test_labor_is_a_quarter_hour_multiple_within_7_5_minutes_of_exact(
    area: AreaInput, labor_rate_cents: int
) -> None:
    result = calculate_estimate(
        EstimateInput(areas=(area,), labor_rate_cents=labor_rate_cents, tax_rate=Decimal("0"))
    )
    hours = result.lines[1].quantity

    with localcontext(prec=EXACT):
        exact = area.quantity * area.coats * area.rates.labor_hours_per_unit
        assert (hours * 4) == (hours * 4).to_integral_value()  # multiple of 0.25
        assert abs(hours - exact) <= Decimal("0.125")


@PROPERTY_SETTINGS
@given(estimate_input=estimate_inputs())
def test_totals_are_internally_consistent(estimate_input: EstimateInput) -> None:
    result = calculate_estimate(estimate_input)

    # Two lines per area, in input order: material then labor.
    assert [(ln.area_id, ln.kind) for ln in result.lines] == [
        (area.area_id, kind) for area in estimate_input.areas for kind in LineKind
    ]
    with localcontext(prec=EXACT):
        for line in result.lines:
            assert line.total_cents >= 0
            assert line.total_cents == round_half_up_to_cents(line.quantity * line.unit_price_cents)

        assert result.subtotal_cents == sum(line.total_cents for line in result.lines)
        assert result.total_cents == result.subtotal_cents + result.tax_cents
        # Tax is the exact amount, off by at most half a cent of rounding.
        assert abs(result.tax_cents - result.subtotal_cents * estimate_input.tax_rate) <= Decimal(
            "0.5"
        )


@PROPERTY_SETTINGS
@given(estimate_input=estimate_inputs())
def test_overrides_change_only_their_own_lines(estimate_input: EstimateInput) -> None:
    with_overrides = calculate_estimate(estimate_input)
    baseline = _without_overrides(estimate_input)
    by_key = {override.line_key: override for override in estimate_input.overrides}

    for line, original in zip(with_overrides.lines, baseline.lines, strict=True):
        override = by_key.get((line.area_id, line.kind))
        if override is None:
            assert line == original  # untouched lines are identical
            continue
        assert line.is_override is True
        expected_quantity = (
            override.quantity if override.quantity is not None else original.quantity
        )
        expected_price = (
            override.unit_price_cents
            if override.unit_price_cents is not None
            else original.unit_price_cents
        )
        assert (line.quantity, line.unit_price_cents) == (expected_quantity, expected_price)
        assert (line.description, line.unit) == (original.description, original.unit)


@PROPERTY_SETTINGS
@given(estimate_input=estimate_inputs())
def test_calculation_is_deterministic(estimate_input: EstimateInput) -> None:
    # Pure function: same input, same output, every time. This is what makes
    # recalculating a quote safe.
    assert calculate_estimate(estimate_input) == calculate_estimate(estimate_input)
