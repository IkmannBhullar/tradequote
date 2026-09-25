"""Tests for the system template seed."""

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import TemplateItem, TradeTemplate
from app.models.enums import MeasureType
from app.seed import INTERIOR_PAINTING, seed_system_templates


def _system_painting_template(session: Session) -> TradeTemplate:
    template = session.scalar(
        select(TradeTemplate).where(
            TradeTemplate.organization_id.is_(None),
            TradeTemplate.name == INTERIOR_PAINTING.name,
        )
    )
    assert template is not None
    return template


def test_seed_creates_system_painting_template(db_session: Session) -> None:
    seed_system_templates(db_session)

    template = _system_painting_template(db_session)
    assert template.trade == "painting"
    assert {item.name for item in template.items} == {
        "Walls",
        "Ceilings",
        "Trim & baseboards",
        "Doors",
        "Primer",
    }
    walls = next(item for item in template.items if item.name == "Walls")
    assert walls.measure_type is MeasureType.AREA
    assert walls.coverage_per_material_unit == Decimal("350")
    assert walls.default_coats == 2


def test_seed_is_idempotent(db_session: Session) -> None:
    seed_system_templates(db_session)
    first_ids = {item.name: item.id for item in _system_painting_template(db_session).items}

    seed_system_templates(db_session)

    assert db_session.scalar(select(func.count()).select_from(TradeTemplate)) == 1
    assert db_session.scalar(select(func.count()).select_from(TemplateItem)) == len(
        INTERIOR_PAINTING.items
    )
    # Same rows updated in place, not deleted and recreated.
    second_ids = {item.name: item.id for item in _system_painting_template(db_session).items}
    assert second_ids == first_ids


def test_reseeding_restores_edited_values(db_session: Session) -> None:
    seed_system_templates(db_session)
    walls = next(i for i in _system_painting_template(db_session).items if i.name == "Walls")
    walls.material_unit_cost_cents = 1
    db_session.flush()

    seed_system_templates(db_session)

    assert walls.material_unit_cost_cents == 4500
