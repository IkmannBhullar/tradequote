"""Integration tests for payments, balances, and the automatic "paid" status."""

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from tests.api_helpers import ApiUser

APPROVE = {"name": "Jane Homeowner", "accept_terms": True}


def business_today() -> str:
    # The API's "today" is in the business timezone. Using this machine's
    # date instead made these tests fail in UTC containers every evening in
    # North America (it's already tomorrow in UTC).
    return datetime.now(ZoneInfo(get_settings().display_timezone)).date().isoformat()


def approved_job(owner: ApiUser, client: TestClient, deposit_cents: int = 10_000) -> str:
    """A job whose $483.00 quote (with a deposit) the client has approved."""
    quote = owner.add_area(owner.create_quote()["id"])
    owner.ok("patch", f"/quotes/{quote['id']}", json={"deposit_required_cents": deposit_cents})
    token = owner.ok("post", f"/quotes/{quote['id']}/send")["link"]["token"]
    response = client.post("/public/quote/approve", headers={"X-Quote-Token": token}, json=APPROVE)
    assert response.status_code == 200, response.text
    job_id: str = quote["job_id"]
    return job_id


def pay(owner: ApiUser, job_id: str, amount_cents: int, kind: str = "final", **extra: Any) -> Any:
    body = {"amount_cents": amount_cents, "kind": kind, "received_on": business_today()}
    return owner.post(f"/jobs/{job_id}/payments", json=body | extra)


def move(owner: ApiUser, job_id: str, *statuses: str) -> None:
    for status in statuses:
        owner.ok("patch", f"/jobs/{job_id}", json={"status": status})


# ---------------------------------------------------------------------------
# Balances
# ---------------------------------------------------------------------------


def test_the_api_reports_today_in_the_business_timezone(owner: ApiUser) -> None:
    job = owner.create_job()
    assert owner.ok("get", f"/jobs/{job['id']}/payments")["today"] == business_today()


def test_nothing_is_owed_before_a_quote_is_approved(owner: ApiUser) -> None:
    job = owner.create_job()

    summary = owner.ok("get", f"/jobs/{job['id']}/payments")["summary"]
    response = pay(owner, job["id"], 100)

    assert summary == {
        "amount_due_cents": None,
        "paid_cents": 0,
        "balance_cents": None,
        "deposit_required_cents": None,
        "deposit_outstanding_cents": None,
    }
    assert response.status_code == 409
    assert "approved quote" in response.json()["detail"]


def test_a_deposit_reduces_the_balance(owner: ApiUser, client: TestClient) -> None:
    job_id = approved_job(owner, client)
    before = owner.ok("get", f"/jobs/{job_id}/payments")["summary"]

    response = pay(owner, job_id, 10_000, kind="deposit", method="e-transfer")

    assert response.status_code == 201
    body = response.json()
    assert (before["amount_due_cents"], before["deposit_outstanding_cents"]) == (48_300, 10_000)
    assert body["summary"] == {
        "amount_due_cents": 48_300,
        "paid_cents": 10_000,
        "balance_cents": 38_300,
        "deposit_required_cents": 10_000,
        "deposit_outstanding_cents": 0,
    }
    assert body["job_status"] == "approved"  # money alone doesn't finish a job
    payment = body["payments"][0]
    assert (payment["kind"], payment["method"], payment["voided_at"]) == (
        "deposit",
        "e-transfer",
        None,
    )


def test_overpaying_is_rejected_with_the_balance(owner: ApiUser, client: TestClient) -> None:
    job_id = approved_job(owner, client)
    pay(owner, job_id, 10_000)

    response = pay(owner, job_id, 38_301)

    assert response.status_code == 422
    assert response.json() == {"detail": "That's more than the remaining balance of $383.00"}


@pytest.mark.parametrize(
    "changes",
    [
        {"amount_cents": 0},
        {"amount_cents": -100},
        {"kind": "refund"},
        {"received_on": "not-a-date"},
    ],
)
def test_invalid_payments_are_422(
    owner: ApiUser, client: TestClient, changes: dict[str, Any]
) -> None:
    job_id = approved_job(owner, client)
    body = {"amount_cents": 100, "kind": "deposit", "received_on": business_today()}
    assert owner.post(f"/jobs/{job_id}/payments", json=body | changes).status_code == 422


def test_future_dates_are_rejected(owner: ApiUser, client: TestClient) -> None:
    job_id = approved_job(owner, client)
    tomorrow = datetime.fromisoformat(business_today()) + timedelta(days=1)
    response = pay(owner, job_id, 100, received_on=tomorrow.date().isoformat())
    assert response.status_code == 422
    assert "future" in response.json()["detail"]


def test_amount_due_follows_the_latest_approved_version(owner: ApiUser, client: TestClient) -> None:
    job_id = approved_job(owner, client)
    v1 = owner.ok("get", f"/jobs/{job_id}/quotes")[0]
    v2 = owner.ok("post", f"/quotes/{v1['id']}/revisions", 201)
    v2 = owner.add_area(v2["id"], name="Hall", quantity="100")
    token = owner.ok("post", f"/quotes/{v2['id']}/send")["link"]["token"]
    client.post("/public/quote/approve", headers={"X-Quote-Token": token}, json=APPROVE)

    summary = owner.ok("get", f"/jobs/{job_id}/payments")["summary"]

    assert summary["amount_due_cents"] == v2["total_cents"] > 48_300


# ---------------------------------------------------------------------------
# The automatic "paid" status
# ---------------------------------------------------------------------------


def test_final_payment_on_a_completed_job_marks_it_paid(owner: ApiUser, client: TestClient) -> None:
    job_id = approved_job(owner, client)
    pay(owner, job_id, 10_000, kind="deposit")
    move(owner, job_id, "scheduled", "in_progress", "completed")

    body = pay(owner, job_id, 38_300).json()

    assert (body["job_status"], body["summary"]["balance_cents"]) == ("paid", 0)
    job = owner.ok("get", f"/jobs/{job_id}")
    # Paid is final: no manual moves out of it.
    assert (job["status"], job["allowed_transitions"]) == ("paid", [])


def test_paying_in_full_early_marks_paid_on_completion(owner: ApiUser, client: TestClient) -> None:
    job_id = approved_job(owner, client)
    move(owner, job_id, "scheduled")
    assert pay(owner, job_id, 48_300).json()["job_status"] == "scheduled"  # work not done yet

    move(owner, job_id, "in_progress")
    completed = owner.ok("patch", f"/jobs/{job_id}", json={"status": "completed"})

    # Completed + nothing owing = paid, straight away.
    assert completed["status"] == "paid"


def test_a_completed_job_with_money_owing_stays_completed(
    owner: ApiUser, client: TestClient
) -> None:
    job_id = approved_job(owner, client)
    move(owner, job_id, "scheduled", "in_progress", "completed")
    assert pay(owner, job_id, 10_000).json()["job_status"] == "completed"


# ---------------------------------------------------------------------------
# Voiding
# ---------------------------------------------------------------------------


class TestVoiding:
    def test_voiding_uncounts_the_payment_and_reopens_the_job(
        self, owner: ApiUser, client: TestClient
    ) -> None:
        job_id = approved_job(owner, client)
        move(owner, job_id, "scheduled", "in_progress", "completed")
        payment = pay(owner, job_id, 48_300).json()["payments"][0]

        body = owner.ok(
            "post",
            f"/jobs/{job_id}/payments/{payment['id']}/void",
            json={"reason": "Cheque bounced"},
        )

        assert body["job_status"] == "completed"  # money is owing again
        assert (body["summary"]["paid_cents"], body["summary"]["balance_cents"]) == (0, 48_300)
        # Still in the history, marked void: nothing is deleted.
        voided = body["payments"][0]
        assert voided["void_reason"] == "Cheque bounced"
        assert voided["voided_at"] is not None

    def test_a_payment_can_be_voided_only_once(self, owner: ApiUser, client: TestClient) -> None:
        job_id = approved_job(owner, client)
        payment = pay(owner, job_id, 100).json()["payments"][0]
        url = f"/jobs/{job_id}/payments/{payment['id']}/void"
        owner.ok("post", url, json={"reason": "Typo"})

        response = owner.post(url, json={"reason": "Typo again"})

        assert response.status_code == 409

    @pytest.mark.parametrize("body", [{}, {"reason": ""}, {"reason": "  x "}])
    def test_voiding_needs_a_reason(
        self, owner: ApiUser, client: TestClient, body: dict[str, str]
    ) -> None:
        job_id = approved_job(owner, client)
        payment = pay(owner, job_id, 100).json()["payments"][0]
        response = owner.post(f"/jobs/{job_id}/payments/{payment['id']}/void", json=body)
        assert response.status_code == 422

    def test_a_payment_belongs_to_its_own_job(self, owner: ApiUser, client: TestClient) -> None:
        job_a = approved_job(owner, client)
        job_b = approved_job(owner, client)
        payment = pay(owner, job_a, 100).json()["payments"][0]

        response = owner.post(
            f"/jobs/{job_b}/payments/{payment['id']}/void", json={"reason": "Wrong job"}
        )

        assert response.status_code == 404
