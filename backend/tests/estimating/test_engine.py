"""Example-based tests for the estimating engine.

Pure functions, so no database or fixtures: build inputs, call, compare.
"""

import dataclasses
import uuid
from decimal import Decimal

import pytest

from app.estimating import (
    AreaInput,
    Estimate,
    EstimatedLine,
    EstimateInput,
    ItemRates,
    LineKind,
    LineOverride,
    calculate_estimate,
)

# ---------------------------------------------------------------------------
# Builders: sensible defaults (the worked example), override what a test needs
# ---------------------------------------------------------------------------


def make_rates(**changes: object) -> ItemRates:
    rates = ItemRates(
        material_name="Wall paint",
        material_unit="gallon",
        material_unit_cost_cents=4500,  # $45.00
        coverage_per_material_unit=Decimal("350"),
        waste_factor=Decimal("0.10"),
        labor_hours_per_unit=Decimal("0.006"),
    )
    return dataclasses.replace(rates, **changes)  # type: ignore[arg-type]


def make_area(
    quantity: str = "420", coats: int = 2, name: str = "Walls", **rate_changes: object
) -> AreaInput:
    return AreaInput(
        area_id=uuid.uuid4(),
        name=name,
        quantity=Decimal(quantity),
        coats=coats,
        rates=make_rates(**rate_changes),
    )


def estimate(
    *areas: AreaInput,
    labor_rate_cents: int = 6500,  # $65.00 / hour
    tax_rate: str = "0.05",
    overrides: tuple[LineOverride, ...] = (),
) -> Estimate:
    return calculate_estimate(
        EstimateInput(
            areas=areas,
            labor_rate_cents=labor_rate_cents,
            tax_rate=Decimal(tax_rate),
            overrides=overrides,
        )
    )


def line(result: Estimate, area: AreaInput, kind: LineKind) -> EstimatedLine:
    return next(ln for ln in result.lines if ln.area_id == area.area_id and ln.kind == kind)


# ---------------------------------------------------------------------------
# The worked example from the Milestone 2 plan
# ---------------------------------------------------------------------------


def test_worked_example() -> None:
    walls = make_area()

    result = estimate(walls)

    # 420 x 2 x 1.10 / 350 = 2.64 -> 3 gallons x $45
    assert result.lines[0] == EstimatedLine(
        area_id=walls.area_id,
        kind=LineKind.MATERIAL,
        description="Walls: Wall paint",
        quantity=Decimal("3"),
        unit="gallon",
        unit_price_cents=4500,
        total_cents=13_500,
        is_override=False,
    )
    # 420 x 2 x 0.006 = 5.04 h -> 5.00 h x $65
    assert result.lines[1] == EstimatedLine(
        area_id=walls.area_id,
        kind=LineKind.LABOR,
        description="Walls: labor",
        quantity=Decimal("5.00"),
        unit="hour",
        unit_price_cents=6500,
        total_cents=32_500,
        is_override=False,
    )
    assert (result.subtotal_cents, result.tax_cents, result.total_cents) == (46_000, 2_300, 48_300)


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------


class TestMaterials:
    @pytest.mark.parametrize(("coats", "gallons"), [(1, 2), (2, 3), (3, 4)])
    def test_coats_multiply_material(self, coats: int, gallons: int) -> None:
        # 420 x coats x 1.10 / 350 = 1.32, 2.64, 3.96
        result = estimate(area := make_area(coats=coats))
        assert line(result, area, LineKind.MATERIAL).quantity == gallons

    def test_waste_can_push_into_another_unit(self) -> None:
        no_waste = make_area("350", coats=1, waste_factor=Decimal("0"))
        with_waste = make_area("350", coats=1, waste_factor=Decimal("0.10"))

        assert line(estimate(no_waste), no_waste, LineKind.MATERIAL).quantity == 1
        assert line(estimate(with_waste), with_waste, LineKind.MATERIAL).quantity == 2

    def test_whole_number_needs_do_not_buy_an_extra_unit(self) -> None:
        # True need: 5 x 3 / 3 = exactly 5 units.
        area = make_area(
            "5", coats=3, coverage_per_material_unit=Decimal("3"), waste_factor=Decimal("0")
        )

        # Dividing *first* (as a naive implementation might) gives
        # 1.666...667 x 3 = 5.000...001, which rounds UP to 6: one wasted can.
        naive = Decimal("5") / Decimal("3") * 3
        assert naive > 5

        assert line(estimate(area), area, LineKind.MATERIAL).quantity == 5

    def test_material_total_is_units_times_unit_cost(self) -> None:
        area = make_area(material_unit_cost_cents=3999)
        material = line(estimate(area), area, LineKind.MATERIAL)
        assert material.total_cents == 3 * 3999

    def test_materials_are_rounded_up_per_area_not_pooled(self) -> None:
        # Design choice 1: rooms may be different colors, so no pooling.
        # 1.2 gal + 0.8 gal = 2 + 1 = 3 gallons (pooled would be 2).
        living = make_area("420", coats=1, waste_factor=Decimal("0"), name="Living")
        bedroom = make_area("280", coats=1, waste_factor=Decimal("0"), name="Bedroom")

        result = estimate(living, bedroom)

        assert line(result, living, LineKind.MATERIAL).quantity == 2
        assert line(result, bedroom, LineKind.MATERIAL).quantity == 1


# ---------------------------------------------------------------------------
# Labor
# ---------------------------------------------------------------------------


class TestLabor:
    @pytest.mark.parametrize(("coats", "hours"), [(1, "2.50"), (2, "5.00"), (3, "7.50")])
    def test_coats_multiply_labor(self, coats: int, hours: str) -> None:
        # 420 x coats x 0.006 = 2.52, 5.04, 7.56 -> nearest quarter
        result = estimate(area := make_area(coats=coats))
        assert line(result, area, LineKind.LABOR).quantity == Decimal(hours)

    def test_tiny_area_rounds_to_zero_labor(self) -> None:
        # Design choice 2 (pending KBS): nearest 0.25 h means 10 sq ft x 2
        # coats x 0.006 = 0.12 h -> 0.00 h -> $0 labor. Documented, not a bug.
        area = make_area("10")
        labor = line(estimate(area), area, LineKind.LABOR)
        assert (labor.quantity, labor.total_cents) == (Decimal("0.00"), 0)

    @pytest.mark.parametrize(
        ("quantity", "rate", "expected_cents"),
        [
            ("20.834", 6501, 1625),  # 0.25 h x 6501 = 1625.25 -> 1625
            ("83.334", 6501, 3251),  # 0.50 h x 6501 = 3250.50 -> 3251 (half-up)
        ],
    )
    def test_fractional_cents_round_half_up(
        self, quantity: str, rate: int, expected_cents: int
    ) -> None:
        # 1 coat, 0.006 h/unit: 20.834 x 0.006 = 0.125004 h -> 0.25 h;
        # 83.334 x 0.006 = 0.500004 h -> 0.50 h
        area = make_area(quantity, coats=1)
        labor = line(estimate(area, labor_rate_cents=rate), area, LineKind.LABOR)
        assert labor.total_cents == expected_cents

    def test_zero_labor_rate_means_free_labor(self) -> None:
        area = make_area()
        labor = line(estimate(area, labor_rate_cents=0), area, LineKind.LABOR)
        assert (labor.quantity, labor.total_cents) == (Decimal("5.00"), 0)


# ---------------------------------------------------------------------------
# Totals and tax
# ---------------------------------------------------------------------------


class TestTotals:
    def test_subtotal_sums_every_line_across_areas(self) -> None:
        result = estimate(make_area(name="A"), make_area(name="B"))
        assert len(result.lines) == 4
        assert result.subtotal_cents == 2 * 46_000
        assert result.total_cents == result.subtotal_cents + result.tax_cents

    def test_zero_tax_rate(self) -> None:
        result = estimate(make_area(), tax_rate="0")
        assert (result.tax_cents, result.total_cents) == (0, 46_000)

    def test_tax_is_rounded_half_up_once_on_the_subtotal(self) -> None:
        # Subtotal 1010 cents x 5% = 50.5 -> 51. Engineered with a $10.10
        # material, zero labor.
        area = make_area(
            "1", coats=1, material_unit_cost_cents=1010, labor_hours_per_unit=Decimal("0")
        )
        result = estimate(area)
        assert (result.subtotal_cents, result.tax_cents, result.total_cents) == (1010, 51, 1061)

    def test_no_areas_means_an_empty_zero_estimate(self) -> None:
        result = estimate()
        assert result == Estimate(lines=(), subtotal_cents=0, tax_cents=0, total_cents=0)

    def test_zero_quantity_area_still_produces_two_zero_lines(self) -> None:
        # Stable line identity: every area always has a material and a labor
        # line, so overrides always have something to attach to.
        area = make_area("0")
        result = estimate(area)
        assert [(ln.kind, ln.quantity, ln.total_cents) for ln in result.lines] == [
            (LineKind.MATERIAL, Decimal("0"), 0),
            (LineKind.LABOR, Decimal("0.00"), 0),
        ]
        assert result.total_cents == 0

    def test_large_jobs_stay_exact(self) -> None:
        # Near the database limit (NUMERIC(12,3)). Python ints never overflow
        # and Decimal never drifts, so the math is exact at any size.
        area = make_area("999999999.999", coats=3)
        result = estimate(area)
        material = line(result, area, LineKind.MATERIAL)
        # 999999999.999 x 3 x 1.10 / 350 = 9428571.428...  -> 9428572
        assert material.quantity == 9_428_572
        assert material.total_cents == 9_428_572 * 4500
        assert result.total_cents == result.subtotal_cents + result.tax_cents


# ---------------------------------------------------------------------------
# Overrides (design choice 3: replace quantity and/or unit price)
# ---------------------------------------------------------------------------


class TestOverrides:
    def test_quantity_override(self) -> None:
        area = make_area()
        override = LineOverride(area.area_id, LineKind.MATERIAL, quantity=Decimal("4"))

        result = estimate(area, overrides=(override,))

        material = line(result, area, LineKind.MATERIAL)
        assert (material.quantity, material.total_cents, material.is_override) == (
            Decimal("4"),
            4 * 4500,
            True,
        )
        # The other line is untouched and not flagged.
        assert line(result, area, LineKind.LABOR).is_override is False
        assert result.subtotal_cents == 18_000 + 32_500

    def test_unit_price_override_keeps_calculated_quantity(self) -> None:
        area = make_area()
        override = LineOverride(area.area_id, LineKind.LABOR, unit_price_cents=5500)

        labor = line(estimate(area, overrides=(override,)), area, LineKind.LABOR)

        assert (labor.quantity, labor.unit_price_cents, labor.total_cents) == (
            Decimal("5.00"),
            5500,
            27_500,
        )
        assert labor.is_override is True

    def test_quantity_and_price_override(self) -> None:
        area = make_area()
        override = LineOverride(
            area.area_id, LineKind.LABOR, quantity=Decimal("2.5"), unit_price_cents=6501
        )

        labor = line(estimate(area, overrides=(override,)), area, LineKind.LABOR)

        # 2.5 x 6501 = 16252.5 -> 16253 (the total is always derived)
        assert labor.total_cents == 16_253

    def test_description_and_unit_are_kept(self) -> None:
        area = make_area()
        override = LineOverride(area.area_id, LineKind.MATERIAL, quantity=Decimal("4"))
        material = line(estimate(area, overrides=(override,)), area, LineKind.MATERIAL)
        assert (material.description, material.unit) == ("Walls: Wall paint", "gallon")

    def test_quantity_override_survives_recalculation(self) -> None:
        # The room was re-measured bigger; the contractor's "4 gallons" stands.
        original = make_area("420")
        remeasured = dataclasses.replace(original, quantity=Decimal("600"))
        override = LineOverride(original.area_id, LineKind.MATERIAL, quantity=Decimal("4"))

        before = line(estimate(original, overrides=(override,)), original, LineKind.MATERIAL)
        after = line(estimate(remeasured, overrides=(override,)), remeasured, LineKind.MATERIAL)

        assert before.quantity == after.quantity == Decimal("4")
        assert after.is_override is True

    def test_price_override_survives_recalculation_with_new_quantity(self) -> None:
        # A negotiated rate sticks, but hours still follow the measurements.
        original = make_area("420")
        remeasured = dataclasses.replace(original, quantity=Decimal("840"))
        override = LineOverride(original.area_id, LineKind.LABOR, unit_price_cents=5500)

        after = line(estimate(remeasured, overrides=(override,)), remeasured, LineKind.LABOR)

        # 840 x 2 x 0.006 = 10.08 -> 10.00 h at the overridden $55
        assert (after.quantity, after.unit_price_cents, after.total_cents) == (
            Decimal("10.00"),
            5500,
            55_000,
        )

    def test_override_for_a_removed_area_is_ignored(self) -> None:
        area = make_area()
        stale = LineOverride(uuid.uuid4(), LineKind.MATERIAL, quantity=Decimal("99"))

        assert estimate(area, overrides=(stale,)) == estimate(area)


# ---------------------------------------------------------------------------
# Input validation: impossible inputs can't even be constructed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("rate_changes", "message"),
    [
        ({"coverage_per_material_unit": Decimal("0")}, "coverage_per_material_unit must be > 0"),
        ({"coverage_per_material_unit": Decimal("-1")}, "coverage_per_material_unit"),
        ({"waste_factor": Decimal("-0.01")}, "waste_factor"),
        ({"labor_hours_per_unit": Decimal("-1")}, "labor_hours_per_unit"),
        ({"labor_hours_per_unit": Decimal("NaN")}, "labor_hours_per_unit"),
        ({"waste_factor": Decimal("Infinity")}, "waste_factor"),
        ({"material_unit_cost_cents": -1}, "material_unit_cost_cents"),
    ],
)
def test_invalid_rates_are_rejected(rate_changes: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        make_rates(**rate_changes)


@pytest.mark.parametrize(
    ("quantity", "coats", "message"),
    [
        ("-1", 2, "quantity"),
        ("NaN", 2, "quantity"),
        ("Infinity", 2, "quantity"),
        ("420", 0, "coats must be >= 1"),
    ],
)
def test_invalid_areas_are_rejected(quantity: str, coats: int, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        make_area(quantity, coats=coats)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({}, "must set quantity, unit_price_cents, or both"),
        ({"quantity": Decimal("-1")}, "override quantity"),
        ({"quantity": Decimal("1.2345")}, "at most 3 decimal places"),
        ({"unit_price_cents": -1}, "override unit_price_cents"),
    ],
)
def test_invalid_overrides_are_rejected(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        LineOverride(uuid.uuid4(), LineKind.MATERIAL, **kwargs)  # type: ignore[arg-type]


def test_override_with_three_decimal_places_is_allowed() -> None:
    override = LineOverride(uuid.uuid4(), LineKind.LABOR, quantity=Decimal("1.125"))
    assert override.quantity == Decimal("1.125")


@pytest.mark.parametrize(
    ("labor_rate_cents", "tax_rate", "message"),
    [
        (-1, "0.05", "labor_rate_cents"),
        (6500, "-0.01", "tax_rate"),
        (6500, "1.01", "tax_rate must be a fraction"),
    ],
)
def test_invalid_estimate_settings_are_rejected(
    labor_rate_cents: int, tax_rate: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        EstimateInput(areas=(), labor_rate_cents=labor_rate_cents, tax_rate=Decimal(tax_rate))


def test_duplicate_area_ids_are_rejected() -> None:
    area = make_area()
    with pytest.raises(ValueError, match="area_id values must be unique"):
        EstimateInput(areas=(area, area), labor_rate_cents=6500, tax_rate=Decimal("0"))


def test_two_overrides_for_the_same_line_are_rejected() -> None:
    area_id = uuid.uuid4()
    overrides = (
        LineOverride(area_id, LineKind.MATERIAL, quantity=Decimal("1")),
        LineOverride(area_id, LineKind.MATERIAL, unit_price_cents=1),
    )
    with pytest.raises(ValueError, match="at most one override"):
        EstimateInput(areas=(), labor_rate_cents=0, tax_rate=Decimal("0"), overrides=overrides)


def test_results_are_immutable() -> None:
    result = estimate(make_area())
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.total_cents = 0  # type: ignore[misc]
