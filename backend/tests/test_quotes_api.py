"""Integration tests for quotes: areas, recalculation, overrides, snapshots,
immutability, and versioning."""

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Quote, TemplateItem
from app.models.enums import QuoteStatus
from app.services import quotes as quote_service
from app.services.context import Tenant
from app.services.errors import ConflictError
from tests.api_helpers import ApiUser


def lines(quote: dict[str, Any]) -> list[tuple[str, str, int]]:
    """(kind, quantity, total_cents) per line, in response order."""
    return [(ln["kind"], ln["quantity"], ln["total_cents"]) for ln in quote["line_items"]]


def totals(quote: dict[str, Any]) -> tuple[int, int, int]:
    return quote["subtotal_cents"], quote["tax_cents"], quote["total_cents"]


def set_status(session: Session, quote_id: str, status: QuoteStatus) -> None:
    """Move a quote out of draft directly in the DB (sending and approving
    arrive in Milestone 6)."""
    quote = session.get(Quote, quote_id)
    assert quote is not None
    quote.status = status
    quote.sent_at = datetime.now(UTC)
    if status is QuoteStatus.APPROVED:
        quote.approved_at, quote.approved_by_name = datetime.now(UTC), "Jane Homeowner"
    if status is QuoteStatus.DECLINED:
        quote.declined_at, quote.declined_by_name = datetime.now(UTC), "Jane Homeowner"
    session.flush()


# ---------------------------------------------------------------------------
# Creating quotes
# ---------------------------------------------------------------------------


class TestCreate:
    def test_first_quote_is_an_empty_draft_with_rate_snapshots(self, owner: ApiUser) -> None:
        quote = owner.create_quote()

        assert (quote["version"], quote["status"]) == (1, "draft")
        assert (quote["labor_rate_cents"], quote["tax_rate"]) == (6500, "0.05000")
        assert quote["areas"] == quote["line_items"] == []
        assert totals(quote) == (0, 0, 0)

    def test_a_job_gets_only_one_first_quote(self, owner: ApiUser) -> None:
        job = owner.create_job()
        owner.create_quote(job["id"])

        response = owner.post(f"/jobs/{job['id']}/quotes")

        assert response.status_code == 409
        assert "create a revision" in response.json()["detail"]

    def test_unknown_job_is_404(self, owner: ApiUser) -> None:
        response = owner.post("/jobs/00000000-0000-0000-0000-000000000000/quotes")
        assert response.status_code == 404


def test_version_race_becomes_a_conflict(
    owner: ApiUser, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Two simultaneous "create quote" requests: both see no existing quote,
    # but the UNIQUE (job_id, version) constraint lets only one insert win.
    job = owner.create_job()
    owner.create_quote(job["id"])
    monkeypatch.setattr(
        "app.repositories.quotes.QuoteRepository.latest_for_job", lambda self, job_id: None
    )
    tenant = Tenant(organization_id=owner.organization_id, user_id=None, role=None)  # type: ignore[arg-type]

    with pytest.raises(ConflictError):
        quote_service.create_first_quote(db_session, tenant, job["id"])


# ---------------------------------------------------------------------------
# Areas and live recalculation
# ---------------------------------------------------------------------------


class TestAreas:
    def test_adding_an_area_prices_the_quote(self, owner: ApiUser) -> None:
        quote = owner.create_quote()

        quote = owner.add_area(quote["id"])  # 420 sq ft walls, default 2 coats

        # The Milestone 2 worked example, now end to end over HTTP.
        area = quote["areas"][0]
        assert (area["coats"], area["measure_type"], area["position"]) == (2, "area", 0)
        assert area["material_unit_cost_cents"] == 4500  # snapshot of the template
        assert lines(quote) == [("material", "3.000", 13_500), ("labor", "5.000", 32_500)]
        assert totals(quote) == (46_000, 2_300, 48_300)
        assert quote["line_items"][0]["description"] == "Living room walls: Interior wall paint"

    def test_coats_can_be_set_explicitly(self, owner: ApiUser) -> None:
        quote = owner.add_area(owner.create_quote()["id"], coats=1)
        assert lines(quote)[0] == ("material", "2.000", 9_000)  # 420 x 1.1 / 350 = 1.32 -> 2

    def test_areas_keep_their_order(self, owner: ApiUser) -> None:
        quote_id = owner.create_quote()["id"]
        for name in ("Kitchen", "Hall", "Bedroom"):
            owner.add_area(quote_id, name=name)

        quote = owner.ok("get", f"/quotes/{quote_id}")

        assert [a["name"] for a in quote["areas"]] == ["Kitchen", "Hall", "Bedroom"]
        # Lines follow the areas: (material, labor) for each, in order.
        assert [ln["description"].split(":")[0] for ln in quote["line_items"]] == [
            "Kitchen", "Kitchen", "Hall", "Hall", "Bedroom", "Bedroom",
        ]  # fmt: skip

    def test_editing_an_area_recalculates_and_keeps_line_ids(self, owner: ApiUser) -> None:
        quote = owner.add_area(owner.create_quote()["id"])
        area_id, line_ids = quote["areas"][0]["id"], [ln["id"] for ln in quote["line_items"]]

        quote = owner.ok(
            "patch", f"/quotes/{quote['id']}/areas/{area_id}", json={"quantity": "840"}
        )

        # 840 x 2 x 1.1 / 350 = 5.28 -> 6 gal; 840 x 2 x 0.006 = 10.08 -> 10 h
        assert lines(quote) == [("material", "6.000", 27_000), ("labor", "10.000", 65_000)]
        assert [ln["id"] for ln in quote["line_items"]] == line_ids

    def test_deleting_an_area_removes_its_lines(self, owner: ApiUser) -> None:
        quote = owner.add_area(owner.create_quote()["id"])

        quote = owner.ok("delete", f"/quotes/{quote['id']}/areas/{quote['areas'][0]['id']}")

        assert quote["areas"] == quote["line_items"] == []
        assert totals(quote) == (0, 0, 0)

    def test_unknown_area_is_404(self, owner: ApiUser) -> None:
        quote = owner.create_quote()
        response = owner.patch(
            f"/quotes/{quote['id']}/areas/00000000-0000-0000-0000-000000000000",
            json={"quantity": "1"},
        )
        assert response.status_code == 404

    def test_area_from_another_quote_is_404(self, owner: ApiUser) -> None:
        first = owner.add_area(owner.create_quote()["id"])
        second = owner.create_quote()

        response = owner.delete(f"/quotes/{second['id']}/areas/{first['areas'][0]['id']}")

        assert response.status_code == 404

    @pytest.mark.parametrize(
        "body",
        [
            {"quantity": "-1"},
            {"quantity": "1.2345"},  # would be silently rounded by NUMERIC(12,3)
            {"coats": 0},
            {"name": None},
        ],
    )
    def test_invalid_area_input_is_422(self, owner: ApiUser, body: dict[str, Any]) -> None:
        quote = owner.add_area(owner.create_quote()["id"])
        response = owner.patch(f"/quotes/{quote['id']}/areas/{quote['areas'][0]['id']}", json=body)
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Overrides
# ---------------------------------------------------------------------------


def _override_url(quote: dict[str, Any], kind: str) -> str:
    line = next(ln for ln in quote["line_items"] if ln["kind"] == kind)
    return f"/quotes/{quote['id']}/line-items/{line['id']}/override"


class TestOverrides:
    def test_quantity_override_survives_remeasuring(self, owner: ApiUser) -> None:
        quote = owner.add_area(owner.create_quote()["id"])
        quote = owner.ok("put", _override_url(quote, "material"), json={"quantity": "4"})
        material = quote["line_items"][0]
        assert (material["quantity"], material["total_cents"], material["is_override"]) == (
            "4.000",
            18_000,
            True,
        )

        # The room is re-measured much bigger; the contractor's 4 gal stands.
        quote = owner.ok(
            "patch",
            f"/quotes/{quote['id']}/areas/{quote['areas'][0]['id']}",
            json={"quantity": "900"},
        )

        assert lines(quote)[0] == ("material", "4.000", 18_000)
        assert quote["line_items"][0]["override_quantity"] == "4.000"

    def test_price_override_keeps_following_the_measurements(self, owner: ApiUser) -> None:
        quote = owner.add_area(owner.create_quote()["id"])
        quote = owner.ok("put", _override_url(quote, "labor"), json={"unit_price_cents": 5500})
        assert lines(quote)[1] == ("labor", "5.000", 27_500)

        quote = owner.ok(
            "patch",
            f"/quotes/{quote['id']}/areas/{quote['areas'][0]['id']}",
            json={"quantity": "840"},
        )

        # Hours recalculated (10 h), negotiated $55 rate kept.
        assert lines(quote)[1] == ("labor", "10.000", 55_000)

    def test_clearing_an_override_restores_the_calculation(self, owner: ApiUser) -> None:
        quote = owner.add_area(owner.create_quote()["id"])
        quote = owner.ok("put", _override_url(quote, "material"), json={"quantity": "4"})

        quote = owner.ok("delete", _override_url(quote, "material"))

        material = quote["line_items"][0]
        assert (material["quantity"], material["is_override"], material["override_quantity"]) == (
            "3.000",
            False,
            None,
        )
        assert totals(quote) == (46_000, 2_300, 48_300)

    def test_put_replaces_the_whole_override(self, owner: ApiUser) -> None:
        quote = owner.add_area(owner.create_quote()["id"])
        owner.ok(
            "put", _override_url(quote, "labor"), json={"quantity": "8", "unit_price_cents": 1}
        )

        quote = owner.ok("put", _override_url(quote, "labor"), json={"unit_price_cents": 5500})

        labor = quote["line_items"][1]
        assert (labor["override_quantity"], labor["quantity"]) == (None, "5.000")

    @pytest.mark.parametrize(
        "body", [{}, {"quantity": "-1"}, {"quantity": "1.2345"}, {"unit_price_cents": -1}]
    )
    def test_invalid_override_is_422(self, owner: ApiUser, body: dict[str, Any]) -> None:
        quote = owner.add_area(owner.create_quote()["id"])
        assert owner.put(_override_url(quote, "material"), json=body).status_code == 422

    def test_unknown_line_is_404(self, owner: ApiUser) -> None:
        quote = owner.create_quote()
        url = f"/quotes/{quote['id']}/line-items/00000000-0000-0000-0000-000000000000/override"
        assert owner.put(url, json={"quantity": "1"}).status_code == 404


# ---------------------------------------------------------------------------
# Deposit
# ---------------------------------------------------------------------------


class TestDeposit:
    def test_deposit_can_be_set_up_to_the_total(self, owner: ApiUser) -> None:
        quote = owner.add_area(owner.create_quote()["id"])

        ok = owner.patch(f"/quotes/{quote['id']}", json={"deposit_required_cents": 48_300})
        too_much = owner.patch(f"/quotes/{quote['id']}", json={"deposit_required_cents": 48_301})

        assert ok.status_code == 200 and ok.json()["deposit_required_cents"] == 48_300
        assert too_much.status_code == 422

    def test_deposit_is_clamped_when_the_total_drops(self, owner: ApiUser) -> None:
        quote = owner.add_area(owner.create_quote()["id"])
        owner.ok("patch", f"/quotes/{quote['id']}", json={"deposit_required_cents": 40_000})

        quote = owner.ok("delete", f"/quotes/{quote['id']}/areas/{quote['areas'][0]['id']}")

        assert quote["deposit_required_cents"] == 0


# ---------------------------------------------------------------------------
# Price snapshots (rule 6)
# ---------------------------------------------------------------------------


class TestSnapshots:
    def test_org_rate_changes_do_not_touch_existing_quotes(self, owner: ApiUser) -> None:
        quote = owner.add_area(owner.create_quote()["id"])
        owner.ok(
            "patch", "/organization", json={"default_labor_rate_cents": 9900, "tax_rate": "0.1"}
        )

        # Even an edit (which recalculates) keeps the quote's own rates.
        quote = owner.ok(
            "patch", f"/quotes/{quote['id']}/areas/{quote['areas'][0]['id']}", json={"name": "Den"}
        )

        assert (quote["labor_rate_cents"], quote["tax_rate"]) == (6500, "0.05000")
        assert totals(quote) == (46_000, 2_300, 48_300)

    def test_template_price_changes_do_not_touch_existing_quotes(
        self, owner: ApiUser, db_session: Session
    ) -> None:
        quote = owner.add_area(owner.create_quote()["id"])
        item = db_session.get(TemplateItem, quote["areas"][0]["template_item_id"])
        assert item is not None
        item.material_unit_cost_cents = 9999
        db_session.flush()

        quote = owner.ok(
            "patch", f"/quotes/{quote['id']}/areas/{quote['areas'][0]['id']}", json={"coats": 2}
        )

        assert lines(quote)[0] == ("material", "3.000", 13_500)  # still $45/gal

    def test_refresh_rates_pulls_in_current_prices(
        self, owner: ApiUser, db_session: Session
    ) -> None:
        quote = owner.add_area(owner.create_quote()["id"])
        item = db_session.get(TemplateItem, quote["areas"][0]["template_item_id"])
        assert item is not None
        item.material_unit_cost_cents = 5000
        db_session.flush()
        owner.ok("patch", "/organization", json={"default_labor_rate_cents": 7000})

        quote = owner.ok("post", f"/quotes/{quote['id']}/refresh-rates")

        assert quote["labor_rate_cents"] == 7000
        assert lines(quote) == [("material", "3.000", 15_000), ("labor", "5.000", 35_000)]

    def test_quote_survives_its_template_item_being_deleted(
        self, owner: ApiUser, db_session: Session
    ) -> None:
        quote = owner.add_area(owner.create_quote()["id"])
        area_id = quote["areas"][0]["id"]
        item = db_session.get(TemplateItem, quote["areas"][0]["template_item_id"])
        db_session.delete(item)
        db_session.flush()

        # Still editable and recalculable from its own snapshot...
        quote = owner.ok(
            "patch", f"/quotes/{quote['id']}/areas/{area_id}", json={"quantity": "840"}
        )
        assert quote["areas"][0]["template_item_id"] is None
        assert lines(quote)[0] == ("material", "6.000", 27_000)
        # ...and refreshing leaves that area's snapshot alone.
        assert (
            owner.ok("post", f"/quotes/{quote['id']}/refresh-rates")["areas"][0][
                "material_unit_cost_cents"
            ]
            == 4500
        )


# ---------------------------------------------------------------------------
# Immutability (rule 7) and versioning
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", [QuoteStatus.SENT, QuoteStatus.APPROVED, QuoteStatus.DECLINED])
def test_non_draft_quotes_cannot_be_edited(
    owner: ApiUser, db_session: Session, status: QuoteStatus
) -> None:
    quote = owner.add_area(owner.create_quote()["id"])
    set_status(db_session, quote["id"], status)
    quote_url = f"/quotes/{quote['id']}"
    area_url = f"{quote_url}/areas/{quote['areas'][0]['id']}"
    new_area = {"template_item_id": owner.template_item_id(), "name": "x", "quantity": "1"}

    attempts = [
        owner.patch(quote_url, json={"deposit_required_cents": 1}),
        owner.post(f"{quote_url}/refresh-rates"),
        owner.post(f"{quote_url}/areas", json=new_area),
        owner.patch(area_url, json={"quantity": "1"}),
        owner.delete(area_url),
        owner.put(_override_url(quote, "labor"), json={"quantity": "1"}),
        owner.delete(_override_url(quote, "labor")),
    ]

    assert [r.status_code for r in attempts] == [409] * len(attempts)
    assert "create a revision" in attempts[0].json()["detail"]
    assert totals(owner.ok("get", quote_url)) == (46_000, 2_300, 48_300)  # unchanged


class TestRevisions:
    def test_revision_copies_areas_rates_and_overrides(
        self, owner: ApiUser, db_session: Session
    ) -> None:
        v1 = owner.add_area(owner.create_quote()["id"], name="Kitchen")
        v1 = owner.add_area(v1["id"], name="Hall", quantity="100")
        v1 = owner.ok("put", _override_url(v1, "material"), json={"quantity": "4"})
        owner.ok("patch", f"/quotes/{v1['id']}", json={"deposit_required_cents": 10_000})
        set_status(db_session, v1["id"], QuoteStatus.SENT)
        v1 = owner.ok("get", f"/quotes/{v1['id']}")

        v2 = owner.ok("post", f"/quotes/{v1['id']}/revisions", 201)

        assert (v2["version"], v2["status"], v2["job_id"]) == (2, "draft", v1["job_id"])
        assert [a["name"] for a in v2["areas"]] == ["Kitchen", "Hall"]
        assert {a["id"] for a in v2["areas"]}.isdisjoint({a["id"] for a in v1["areas"]})
        assert v2["line_items"][0]["override_quantity"] == "4.000"
        assert (v2["deposit_required_cents"], totals(v2)) == (10_000, totals(v1))

    def test_editing_a_revision_leaves_the_original_alone(
        self, owner: ApiUser, db_session: Session
    ) -> None:
        v1 = owner.add_area(owner.create_quote()["id"])
        set_status(db_session, v1["id"], QuoteStatus.APPROVED)
        v2 = owner.ok("post", f"/quotes/{v1['id']}/revisions", 201)

        owner.ok(
            "patch", f"/quotes/{v2['id']}/areas/{v2['areas'][0]['id']}", json={"quantity": "840"}
        )

        assert totals(owner.ok("get", f"/quotes/{v1['id']}")) == (46_000, 2_300, 48_300)
        versions = owner.ok("get", f"/jobs/{v1['job_id']}/quotes")
        assert [(q["version"], q["status"]) for q in versions] == [(1, "approved"), (2, "draft")]

    def test_a_draft_cannot_be_revised(self, owner: ApiUser) -> None:
        quote = owner.create_quote()
        response = owner.post(f"/quotes/{quote['id']}/revisions")
        assert response.status_code == 409
        assert "edit it instead" in response.json()["detail"]

    def test_only_the_latest_version_can_be_revised(
        self, owner: ApiUser, db_session: Session
    ) -> None:
        v1 = owner.create_quote()
        set_status(db_session, v1["id"], QuoteStatus.DECLINED)
        v2 = owner.ok("post", f"/quotes/{v1['id']}/revisions", 201)
        set_status(db_session, v2["id"], QuoteStatus.SENT)

        response = owner.post(f"/quotes/{v1['id']}/revisions")

        assert response.status_code == 409
        assert "latest version" in response.json()["detail"]

    def test_versions_are_stored_as_separate_rows(
        self, owner: ApiUser, db_session: Session
    ) -> None:
        v1 = owner.create_quote()
        set_status(db_session, v1["id"], QuoteStatus.SENT)
        owner.ok("post", f"/quotes/{v1['id']}/revisions", 201)

        rows = db_session.scalars(select(Quote).where(Quote.job_id == v1["job_id"])).all()
        assert sorted(q.version for q in rows) == [1, 2]
