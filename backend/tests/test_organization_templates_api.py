"""Integration tests for /organization and /templates."""

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TradeTemplate, User
from app.models.enums import UserRole
from tests.api_helpers import ApiUser


class TestOrganization:
    def test_owner_updates_settings(self, owner: ApiUser) -> None:
        updated = owner.ok(
            "patch",
            "/organization",
            json={"name": "KBS Painting", "logo_url": "https://example.com/logo.png"},
        )

        assert updated["name"] == "KBS Painting"
        assert updated["logo_url"] == "https://example.com/logo.png"
        # Fields not sent are untouched (set by the fixture).
        assert (updated["default_labor_rate_cents"], updated["tax_rate"]) == (6500, "0.05000")

    def test_response_shows_the_stored_value(self, owner: ApiUser) -> None:
        # Regression: responses once echoed the in-memory Decimal("0.07")
        # instead of what NUMERIC(6,5) stores, so a later GET disagreed.
        patched = owner.ok("patch", "/organization", json={"tax_rate": "0.07"})
        assert patched["tax_rate"] == "0.07000"
        assert owner.ok("get", "/me")["organization"]["tax_rate"] == "0.07000"

    def test_logo_can_be_cleared(self, owner: ApiUser) -> None:
        owner.ok("patch", "/organization", json={"logo_url": "https://example.com/logo.png"})
        assert owner.ok("patch", "/organization", json={"logo_url": None})["logo_url"] is None

    def test_staff_cannot_change_settings(self, owner: ApiUser, db_session: Session) -> None:
        user = db_session.scalar(select(User).where(User.email == "owner@org-a.example.com"))
        assert user is not None
        user.role = UserRole.STAFF
        db_session.flush()

        response = owner.patch("/organization", json={"default_labor_rate_cents": 1})

        assert response.status_code == 403

    @pytest.mark.parametrize(
        "body",
        [
            {"tax_rate": "1.5"},
            {"tax_rate": "0.123456"},  # more precision than NUMERIC(6,5)
            {"default_labor_rate_cents": -1},
            {"name": None},
            {"logo_url": "not a url"},
        ],
    )
    def test_invalid_settings_are_422(self, owner: ApiUser, body: dict[str, Any]) -> None:
        assert owner.patch("/organization", json=body).status_code == 422


class TestTemplates:
    def test_lists_system_templates_with_items(self, owner: ApiUser) -> None:
        templates = owner.ok("get", "/templates")

        system = [t for t in templates if t["organization_id"] is None]
        assert [(t["trade"], t["name"]) for t in system] == [("painting", "Interior Painting")]
        walls = next(i for i in system[0]["items"] if i["name"] == "Walls")
        assert (walls["measure_type"], walls["coverage_per_material_unit"]) == ("area", "350.000")

    def test_own_templates_are_listed_first_and_others_never(
        self, owner: ApiUser, other_owner: ApiUser, db_session: Session
    ) -> None:
        db_session.add_all(
            [
                TradeTemplate(organization_id=owner.organization_id, trade="painting", name="Mine"),
                TradeTemplate(
                    organization_id=other_owner.organization_id, trade="painting", name="Theirs"
                ),
            ]
        )
        db_session.flush()

        names = [t["name"] for t in owner.ok("get", "/templates")]

        assert names == ["Mine", "Interior Painting"]
