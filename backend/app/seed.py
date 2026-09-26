"""Seed the database with system-default trade templates.

Run with:  make seed   (or: cd backend && uv run python -m app.seed)

System templates have organization_id = NULL; organizations copy them to get
their own editable version. The script is idempotent (an "upsert"): running
it again updates existing rows to match the values below instead of creating
duplicates, so it's safe to run on every deploy.

!!! Every number below is a PLACEHOLDER until KBS Painting provides real
!!! coverage, labor, and pricing figures. Don't quote real jobs with them.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_engine
from app.models import TemplateItem, TradeTemplate
from app.models.enums import MeasureType


@dataclass(frozen=True)
class TemplateItemSeed:
    name: str
    measure_type: MeasureType
    material_name: str
    material_unit: str
    material_unit_cost_cents: int
    coverage_per_material_unit: Decimal
    waste_factor: Decimal
    labor_hours_per_unit: Decimal
    default_coats: int


@dataclass(frozen=True)
class TemplateSeed:
    trade: str
    name: str
    items: tuple[TemplateItemSeed, ...]


# Decimals are built from strings: Decimal(0.1) would inherit float error
# (0.1000000000000000055...), while Decimal("0.1") is exactly 0.1.
INTERIOR_PAINTING = TemplateSeed(
    trade="painting",
    name="Interior Painting",
    items=(
        TemplateItemSeed(
            name="Walls",
            measure_type=MeasureType.AREA,  # square feet
            material_name="Interior wall paint",
            material_unit="gallon",
            material_unit_cost_cents=4500,  # $45.00 / gallon
            coverage_per_material_unit=Decimal("350"),  # sq ft per gallon per coat
            waste_factor=Decimal("0.10"),
            labor_hours_per_unit=Decimal("0.00600"),  # ~167 sq ft/hour per coat
            default_coats=2,
        ),
        TemplateItemSeed(
            name="Ceilings",
            measure_type=MeasureType.AREA,
            material_name="Flat ceiling paint",
            material_unit="gallon",
            material_unit_cost_cents=4000,
            coverage_per_material_unit=Decimal("350"),
            waste_factor=Decimal("0.10"),
            labor_hours_per_unit=Decimal("0.00800"),  # overhead work is slower
            default_coats=2,
        ),
        TemplateItemSeed(
            name="Trim & baseboards",
            measure_type=MeasureType.LINEAR,  # linear feet
            material_name="Semi-gloss trim paint",
            material_unit="gallon",
            material_unit_cost_cents=5500,
            coverage_per_material_unit=Decimal("400"),  # linear ft per gallon
            waste_factor=Decimal("0.10"),
            labor_hours_per_unit=Decimal("0.02000"),
            default_coats=2,
        ),
        TemplateItemSeed(
            name="Doors",
            measure_type=MeasureType.COUNT,  # number of doors
            material_name="Semi-gloss door paint",
            material_unit="gallon",
            material_unit_cost_cents=5500,
            coverage_per_material_unit=Decimal("8"),  # doors per gallon (both sides)
            waste_factor=Decimal("0.10"),
            labor_hours_per_unit=Decimal("0.75000"),
            default_coats=2,
        ),
        TemplateItemSeed(
            name="Primer",
            measure_type=MeasureType.AREA,
            material_name="Interior primer",
            material_unit="gallon",
            material_unit_cost_cents=3500,
            coverage_per_material_unit=Decimal("300"),
            waste_factor=Decimal("0.10"),
            labor_hours_per_unit=Decimal("0.00400"),
            default_coats=1,
        ),
    ),
)

# Milestone 8: the second trade, added with data only (architecture rule 5).
# Flooring has no "coats": every item uses 1, so the coats multiplier in the
# formulas is simply x1.
FLOORING = TemplateSeed(
    trade="flooring",
    name="Flooring",
    items=(
        TemplateItemSeed(
            name="Laminate plank",
            measure_type=MeasureType.AREA,  # square feet of floor
            material_name="Laminate flooring",
            material_unit="box",
            material_unit_cost_cents=5500,  # $55.00 / box
            coverage_per_material_unit=Decimal("20"),  # sq ft per box
            waste_factor=Decimal("0.10"),  # cuts and offcuts
            labor_hours_per_unit=Decimal("0.04000"),  # ~25 sq ft/hour
            default_coats=1,
        ),
        TemplateItemSeed(
            name="Engineered hardwood",
            measure_type=MeasureType.AREA,
            material_name="Engineered hardwood",
            material_unit="box",
            material_unit_cost_cents=12000,
            coverage_per_material_unit=Decimal("20"),
            waste_factor=Decimal("0.08"),
            labor_hours_per_unit=Decimal("0.06000"),
            default_coats=1,
        ),
        TemplateItemSeed(
            name="Underlayment",
            measure_type=MeasureType.AREA,
            material_name="Foam underlayment",
            material_unit="roll",
            material_unit_cost_cents=3500,
            coverage_per_material_unit=Decimal("100"),  # sq ft per roll
            waste_factor=Decimal("0.05"),
            labor_hours_per_unit=Decimal("0.00500"),
            default_coats=1,
        ),
        TemplateItemSeed(
            name="Baseboard",
            measure_type=MeasureType.LINEAR,  # linear feet of wall
            material_name="MDF baseboard (8 ft)",
            material_unit="piece",
            material_unit_cost_cents=1200,
            coverage_per_material_unit=Decimal("8"),  # linear ft per piece
            waste_factor=Decimal("0.10"),
            labor_hours_per_unit=Decimal("0.05000"),
            default_coats=1,
        ),
        TemplateItemSeed(
            name="Transition strips",
            measure_type=MeasureType.COUNT,  # number of doorways
            material_name="Transition strip",
            material_unit="piece",
            material_unit_cost_cents=2500,
            coverage_per_material_unit=Decimal("1"),  # one strip per doorway
            waste_factor=Decimal("0"),
            labor_hours_per_unit=Decimal("0.50000"),
            default_coats=1,
        ),
    ),
)

SYSTEM_TEMPLATES: tuple[TemplateSeed, ...] = (INTERIOR_PAINTING, FLOORING)


def upsert_system_template(session: Session, seed: TemplateSeed) -> TradeTemplate:
    """Create or update one system template and its items to match `seed`.

    Items are matched by name. Items that exist in the database but not in
    the seed are left alone, never deleted: a seed script shouldn't destroy
    data it didn't create.
    """
    template = session.scalar(
        select(TradeTemplate).where(
            TradeTemplate.organization_id.is_(None),
            TradeTemplate.trade == seed.trade,
            TradeTemplate.name == seed.name,
        )
    )
    if template is None:
        template = TradeTemplate(organization_id=None, trade=seed.trade, name=seed.name)
        session.add(template)

    existing_items = {item.name: item for item in template.items}
    for item_seed in seed.items:
        item = existing_items.get(item_seed.name)
        if item is None:
            item = TemplateItem(name=item_seed.name)
            template.items.append(item)
        # Assigning an unchanged value is a no-op for SQLAlchemy (no UPDATE is
        # sent), so re-running the seed doesn't touch updated_at needlessly.
        item.measure_type = item_seed.measure_type
        item.material_name = item_seed.material_name
        item.material_unit = item_seed.material_unit
        item.material_unit_cost_cents = item_seed.material_unit_cost_cents
        item.coverage_per_material_unit = item_seed.coverage_per_material_unit
        item.waste_factor = item_seed.waste_factor
        item.labor_hours_per_unit = item_seed.labor_hours_per_unit
        item.default_coats = item_seed.default_coats

    session.flush()
    return template


def seed_system_templates(session: Session) -> None:
    for template_seed in SYSTEM_TEMPLATES:
        upsert_system_template(session, template_seed)


def main() -> None:
    # One transaction for the whole seed: it either fully applies or not at all.
    with Session(get_engine()) as session, session.begin():
        seed_system_templates(session)
    print(f"Seeded {len(SYSTEM_TEMPLATES)} system template(s).")


if __name__ == "__main__":
    main()
