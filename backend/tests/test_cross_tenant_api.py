"""Architecture rule 2 over HTTP: org B can't read or modify ANY of org A's data.

Org A (`owner`) creates one of everything. Org B (`other_owner`) then calls
every endpoint with org A's ids. Each call must be a 404, exactly like an id
that doesn't exist, so org B can't even learn that the ids are real. Finally,
org A's data must be unchanged.
"""

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.models import Payment, TemplateItem, TradeTemplate
from app.models.enums import MeasureType, PaymentKind
from tests.api_helpers import ApiUser


@pytest.fixture
def org_a_data(owner: ApiUser, db_session: Session) -> dict[str, str]:
    client = owner.create_client()
    job = owner.create_job(client["id"])
    quote = owner.add_area(owner.create_quote(job["id"])["id"])

    # A template private to org A.
    template = TradeTemplate(organization_id=owner.organization_id, trade="painting", name="A only")
    template.items.append(
        TemplateItem(
            name="Secret walls",
            measure_type=MeasureType.AREA,
            material_name="Paint",
            material_unit="gallon",
            material_unit_cost_cents=1,
            coverage_per_material_unit=Decimal("1"),
            waste_factor=Decimal("0"),
            labor_hours_per_unit=Decimal("0"),
            default_coats=1,
        )
    )
    db_session.add(template)
    # And a payment on org A's job (added directly: the quote isn't approved).
    payment = Payment(
        organization_id=owner.organization_id,
        job_id=job["id"],
        amount_cents=100,
        kind=PaymentKind.DEPOSIT,
        received_on=date.today(),
    )
    db_session.add(payment)
    db_session.flush()

    return {
        "client": client["id"],
        "job": job["id"],
        "quote": quote["id"],
        "area": quote["areas"][0]["id"],
        "line": quote["line_items"][0]["id"],
        "template_item": str(template.items[0].id),
        "payment": str(payment.id),
    }


_NEW_PAYMENT = {"amount_cents": 100, "kind": "final", "received_on": "2026-01-01"}
_NEW_AREA = {"template_item_id": "{template_item}", "name": "x", "quantity": "1"}

# (method, url template, json body). Bodies are valid, so a 404 can only mean
# "not yours", never "bad input".
ENDPOINTS: list[tuple[str, str, dict[str, Any] | None]] = [
    ("get", "/clients/{client}", None),
    ("patch", "/clients/{client}", {"name": "Hacked"}),
    ("delete", "/clients/{client}", None),
    ("get", "/jobs/{job}", None),
    ("patch", "/jobs/{job}", {"title": "Hacked"}),
    ("get", "/jobs/{job}/quotes", None),
    ("post", "/jobs/{job}/quotes", None),
    ("get", "/quotes/{quote}", None),
    ("patch", "/quotes/{quote}", {"deposit_required_cents": 0}),
    ("post", "/quotes/{quote}/revisions", None),
    ("post", "/quotes/{quote}/refresh-rates", None),
    ("post", "/quotes/{quote}/areas", _NEW_AREA),
    ("patch", "/quotes/{quote}/areas/{area}", {"quantity": "1"}),
    ("delete", "/quotes/{quote}/areas/{area}", None),
    ("put", "/quotes/{quote}/line-items/{line}/override", {"quantity": "1"}),
    ("delete", "/quotes/{quote}/line-items/{line}/override", None),
    ("get", "/jobs/{job}/payments", None),
    ("post", "/jobs/{job}/payments", _NEW_PAYMENT),
    ("post", "/jobs/{job}/payments/{payment}/void", {"reason": "Not yours"}),
]


def _fill(value: Any, ids: dict[str, str]) -> Any:
    if isinstance(value, str):
        return value.format(**ids)
    if isinstance(value, dict):
        return {key: _fill(item, ids) for key, item in value.items()}
    return value


@pytest.mark.parametrize(
    ("method", "url", "body"), ENDPOINTS, ids=[f"{m.upper()} {u}" for m, u, _ in ENDPOINTS]
)
def test_other_org_gets_404_everywhere(
    owner: ApiUser,
    other_owner: ApiUser,
    org_a_data: dict[str, str],
    method: str,
    url: str,
    body: dict[str, Any] | None,
) -> None:
    before = owner.ok("get", f"/quotes/{org_a_data['quote']}")

    kwargs = {"json": _fill(body, org_a_data)} if body is not None else {}
    response = getattr(other_owner, method)(_fill(url, org_a_data), **kwargs)

    assert response.status_code == 404, response.text
    # Org A's data is untouched.
    assert owner.ok("get", f"/quotes/{org_a_data['quote']}") == before
    assert owner.ok("get", f"/clients/{org_a_data['client']}")["name"] == "Jane Homeowner"
    assert owner.ok("get", f"/jobs/{org_a_data['job']}")["title"] == "Repaint living room"
    payments = owner.ok("get", f"/jobs/{org_a_data['job']}/payments")["payments"]
    assert [(p["amount_cents"], p["voided_at"]) for p in payments] == [(100, None)]


def test_lists_never_include_another_orgs_rows(
    other_owner: ApiUser, org_a_data: dict[str, str]
) -> None:
    assert other_owner.ok("get", "/clients")["total"] == 0
    assert other_owner.ok("get", "/jobs")["total"] == 0
    assert "A only" not in [t["name"] for t in other_owner.ok("get", "/templates")]


def test_cannot_attach_own_job_to_another_orgs_client(
    other_owner: ApiUser, org_a_data: dict[str, str]
) -> None:
    response = other_owner.post("/jobs", json={"client_id": org_a_data["client"], "title": "x"})
    assert response.status_code == 404


def test_cannot_price_own_quote_with_another_orgs_template(
    other_owner: ApiUser, org_a_data: dict[str, str]
) -> None:
    quote = other_owner.create_quote()
    response = other_owner.post(
        f"/quotes/{quote['id']}/areas",
        json={"template_item_id": org_a_data["template_item"], "name": "x", "quantity": "1"},
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Template item not found"}


def test_settings_changes_stay_in_own_org(owner: ApiUser, other_owner: ApiUser) -> None:
    other_owner.ok("patch", "/organization", json={"default_labor_rate_cents": 1})
    assert owner.ok("get", "/me")["organization"]["default_labor_rate_cents"] == 6500
