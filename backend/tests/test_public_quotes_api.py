"""Sending quotes, public links, client approval/decline, rate limits, PDFs."""

import hashlib
import io
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import Job, Quote
from app.models.enums import JobStatus
from tests.api_helpers import ApiUser


def send(owner: ApiUser, quote_id: str) -> str:
    """Send a quote and return the raw link token."""
    token: str = owner.ok("post", f"/quotes/{quote_id}/send")["link"]["token"]
    return token


def priced_quote(owner: ApiUser) -> dict[str, Any]:
    return owner.add_area(owner.create_quote()["id"])  # $483.00


def public(client: TestClient, method: str, path: str, token: str, **kwargs: Any) -> Any:
    """Call a public endpoint as the client would: no login, token header."""
    return getattr(client, method)(f"/public{path}", headers={"X-Quote-Token": token}, **kwargs)


APPROVE = {"name": "Jane Homeowner", "accept_terms": True}


# ---------------------------------------------------------------------------
# Sending and links
# ---------------------------------------------------------------------------


class TestSending:
    def test_send_freezes_the_quote_and_returns_a_link_once(
        self, owner: ApiUser, db_session: Session
    ) -> None:
        quote = priced_quote(owner)

        sent = owner.ok("post", f"/quotes/{quote['id']}/send")

        assert sent["quote"]["status"] == "sent"
        assert sent["quote"]["sent_at"] is not None
        token = sent["link"]["token"]
        assert len(token) == 43  # 32 random bytes, URL-safe base64
        expires = datetime.fromisoformat(sent["link"]["expires_at"])
        assert timedelta(days=29) < expires - datetime.now(UTC) <= timedelta(days=30)
        # The quote can no longer be edited.
        assert (
            owner.patch(f"/quotes/{quote['id']}", json={"deposit_required_cents": 0}).status_code
            == 409
        )

    def test_only_a_hash_of_the_token_is_stored(self, owner: ApiUser, db_session: Session) -> None:
        quote = priced_quote(owner)
        token = send(owner, quote["id"])

        row = db_session.get(Quote, quote["id"])
        assert row is not None
        assert row.public_token_hash == hashlib.sha256(token.encode()).hexdigest()
        # The raw token appears in no column of the row.
        assert token not in {str(value) for value in vars(row).values()}

    def test_empty_quotes_cannot_be_sent(self, owner: ApiUser) -> None:
        quote = owner.create_quote()
        response = owner.post(f"/quotes/{quote['id']}/send")
        assert response.status_code == 409
        assert "at least one area" in response.json()["detail"]

    def test_a_sent_quote_cannot_be_sent_again(self, owner: ApiUser) -> None:
        quote = priced_quote(owner)
        send(owner, quote["id"])
        assert owner.post(f"/quotes/{quote['id']}/send").status_code == 409

    def test_new_link_replaces_the_old_one(self, owner: ApiUser, client: TestClient) -> None:
        quote = priced_quote(owner)
        old = send(owner, quote["id"])

        new = owner.ok("post", f"/quotes/{quote['id']}/share-link")["token"]

        assert new != old
        assert public(client, "get", "/quote", old).status_code == 404
        assert public(client, "get", "/quote", new).status_code == 200

    def test_drafts_have_no_link_to_regenerate(self, owner: ApiUser) -> None:
        quote = priced_quote(owner)
        assert owner.post(f"/quotes/{quote['id']}/share-link").status_code == 409


# ---------------------------------------------------------------------------
# Viewing a quote through its link
# ---------------------------------------------------------------------------

PUBLIC_FIELDS = {
    "organization_name", "client_name", "job_title", "job_address", "version", "status",
    "lines", "subtotal_cents", "tax_rate", "tax_cents", "total_cents",
    "deposit_required_cents", "sent_at", "approved_at", "approved_by_name", "declined_at",
    "declined_by_name", "link_expires_at", "is_latest_version", "can_decide",
}  # fmt: skip


class TestPublicView:
    def test_shows_the_quote_and_only_public_fields(
        self, owner: ApiUser, client: TestClient
    ) -> None:
        token = send(owner, priced_quote(owner)["id"])

        response = public(client, "get", "/quote", token)

        assert response.status_code == 200
        body = response.json()
        # Exactly these fields: no ids, rate snapshots, or override details.
        assert set(body) == PUBLIC_FIELDS
        assert set(body["lines"][0]) == {
            "description", "quantity", "unit", "unit_price_cents", "total_cents",
        }  # fmt: skip
        assert (body["organization_name"], body["client_name"]) == ("Org A", "Jane Homeowner")
        assert (body["total_cents"], body["status"], body["can_decide"]) == (48300, "sent", True)
        # Private data behind a secret link: never cached or indexed.
        assert response.headers["Cache-Control"] == "private, no-store"
        assert response.headers["X-Robots-Tag"] == "noindex"

    def test_needs_no_login(self, owner: ApiUser, client: TestClient) -> None:
        token = send(owner, priced_quote(owner)["id"])
        response = client.get("/public/quote", headers={"X-Quote-Token": token})
        assert response.status_code == 200

    @pytest.mark.parametrize(
        ("headers", "status"),
        [
            ({"X-Quote-Token": "x" * 43}, 404),  # well-formed but unknown
            ({"X-Quote-Token": "short"}, 422),
            ({}, 422),  # no token at all
        ],
    )
    def test_bad_tokens(self, client: TestClient, headers: dict[str, str], status: int) -> None:
        assert client.get("/public/quote", headers=headers).status_code == status

    def test_expired_link_is_410(
        self, owner: ApiUser, client: TestClient, db_session: Session
    ) -> None:
        quote = priced_quote(owner)
        token = send(owner, quote["id"])
        row = db_session.get(Quote, quote["id"])
        assert row is not None
        row.token_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db_session.flush()

        response = public(client, "get", "/quote", token)

        assert response.status_code == 410
        assert "expired" in response.json()["detail"]
        assert public(client, "post", "/quote/approve", token, json=APPROVE).status_code == 410


# ---------------------------------------------------------------------------
# Approve / decline
# ---------------------------------------------------------------------------


class TestDecisions:
    def test_approval_records_the_signature_and_moves_the_job(
        self, owner: ApiUser, client: TestClient
    ) -> None:
        quote = priced_quote(owner)
        token = send(owner, quote["id"])

        response = public(client, "post", "/quote/approve", token, json=APPROVE)

        assert response.status_code == 200
        body = response.json()
        assert (body["status"], body["approved_by_name"], body["can_decide"]) == (
            "approved",
            "Jane Homeowner",
            False,
        )
        # The contractor sees it too, and the job moved on the board.
        assert owner.ok("get", f"/quotes/{quote['id']}")["approved_by_name"] == "Jane Homeowner"
        job = owner.ok("get", f"/jobs/{quote['job_id']}")
        assert (job["status"], job["allowed_transitions"]) == ("approved", ["scheduled"])

    @pytest.mark.parametrize(
        "body",
        [
            {"name": "Jane", "accept_terms": False},  # must tick "I agree"
            {"name": "Jane"},
            {"name": " J ", "accept_terms": True},  # a real name, please
            {"accept_terms": True},
        ],
    )
    def test_approval_needs_a_name_and_agreement(
        self, owner: ApiUser, client: TestClient, body: dict[str, Any]
    ) -> None:
        token = send(owner, priced_quote(owner)["id"])
        assert public(client, "post", "/quote/approve", token, json=body).status_code == 422
        assert public(client, "get", "/quote", token).json()["status"] == "sent"

    def test_decline_records_reason_and_leaves_the_job_quoted(
        self, owner: ApiUser, client: TestClient, db_session: Session
    ) -> None:
        quote = priced_quote(owner)
        token = send(owner, quote["id"])

        body = public(
            client,
            "post",
            "/quote/decline",
            token,
            json={"name": "Jane Homeowner", "reason": "Too expensive"},
        ).json()

        assert (body["status"], body["declined_by_name"]) == ("declined", "Jane Homeowner")
        contractor_view = owner.ok("get", f"/quotes/{quote['id']}")
        assert contractor_view["decline_reason"] == "Too expensive"
        job = db_session.get(Job, quote["job_id"])
        assert job is not None and job.status is JobStatus.QUOTED

    def test_a_quote_is_decided_only_once(self, owner: ApiUser, client: TestClient) -> None:
        token = send(owner, priced_quote(owner)["id"])
        public(client, "post", "/quote/approve", token, json=APPROVE)

        again = public(client, "post", "/quote/approve", token, json=APPROVE)
        decline = public(client, "post", "/quote/decline", token, json={"name": "Jane"})

        assert again.status_code == decline.status_code == 409
        assert "already been approved" in again.json()["detail"]
        # Still viewable afterwards, showing the outcome.
        assert public(client, "get", "/quote", token).json()["status"] == "approved"

    def test_a_superseded_version_cannot_be_approved(
        self, owner: ApiUser, client: TestClient
    ) -> None:
        v1 = priced_quote(owner)
        token = send(owner, v1["id"])
        owner.ok("post", f"/quotes/{v1['id']}/revisions", 201)  # v2 replaces it

        view = public(client, "get", "/quote", token).json()
        response = public(client, "post", "/quote/approve", token, json=APPROVE)

        assert (view["is_latest_version"], view["can_decide"]) == (False, False)
        assert response.status_code == 409
        assert "newer version" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Rate limits (rule 8)
# ---------------------------------------------------------------------------


def _limits(app: FastAPI, **changes: int) -> None:
    settings: Settings = get_settings().model_copy(update=changes)
    app.dependency_overrides[get_settings] = lambda: settings


class TestRateLimits:
    def test_public_requests_are_limited_per_ip(
        self, app: FastAPI, owner: ApiUser, client: TestClient
    ) -> None:
        token = send(owner, priced_quote(owner)["id"])
        _limits(app, public_requests_per_minute=3)

        statuses = [
            public(client, "get", "/quote", token).status_code,
            public(client, "get", "/quote", "x" * 43).status_code,  # failed guesses count too
            public(client, "get", "/quote", token).status_code,
        ]
        blocked = public(client, "get", "/quote", token)

        assert statuses == [200, 404, 200]
        assert blocked.status_code == 429
        assert 1 <= int(blocked.headers["Retry-After"]) <= 60

    def test_decisions_are_limited_per_link(
        self, app: FastAPI, owner: ApiUser, client: TestClient
    ) -> None:
        token = send(owner, priced_quote(owner)["id"])
        _limits(app, quote_decisions_per_hour=2)
        bad = {"name": "J", "accept_terms": True}  # rejected (422), but still counted

        first = public(client, "post", "/quote/approve", token, json=bad)
        second = public(client, "post", "/quote/decline", token, json={"name": "J"})
        third = public(client, "post", "/quote/approve", token, json=APPROVE)

        assert (first.status_code, second.status_code, third.status_code) == (422, 422, 429)


# ---------------------------------------------------------------------------
# PDFs (need WeasyPrint's system libraries; see the `pdf` marker)
# ---------------------------------------------------------------------------


def pdf_text(content: bytes) -> str:
    """The PDF's text with ALL whitespace removed.

    PDFs store positioned glyphs, not words; text extraction guesses spaces
    from the gaps. Font kerning (e.g. tucking "a" under "T" in "Tax") can
    fool it into "T ax", so compare text with whitespace squeezed out.
    """
    text = "".join(page.extract_text() for page in PdfReader(io.BytesIO(content)).pages)
    return "".join(text.split())


def squashed(text: str) -> str:
    return "".join(text.split())


@pytest.mark.pdf
class TestPdfs:
    def test_contractor_downloads_a_pdf(self, owner: ApiUser, client: TestClient) -> None:
        quote = priced_quote(owner)

        response = owner.get(f"/quotes/{quote['id']}/pdf")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.headers["content-disposition"] == 'inline; filename="quote-v1.pdf"'
        assert response.content.startswith(b"%PDF")
        text = pdf_text(response.content)
        for expected in ("Org A", "Jane Homeowner", "Living room walls: Interior wall paint",
                         "$135.00", "$460.00", "$23.00", "$483.00", "Tax (5%)"):  # fmt: skip
            assert squashed(expected) in text

    def test_client_downloads_the_pdf_with_the_approval(
        self, owner: ApiUser, client: TestClient
    ) -> None:
        token = send(owner, priced_quote(owner)["id"])
        public(client, "post", "/quote/approve", token, json=APPROVE)

        response = public(client, "get", "/quote/pdf", token)

        assert response.status_code == 200
        assert squashed("Approved by Jane Homeowner") in pdf_text(response.content)

    def test_user_text_is_escaped_not_rendered(self, owner: ApiUser) -> None:
        client_row = owner.ok("post", "/clients", 201, json={"name": "<b>Bob</b> & Co"})
        quote = owner.add_area(owner.create_quote(owner.create_job(client_row["id"])["id"])["id"])

        text = pdf_text(owner.get(f"/quotes/{quote['id']}/pdf").content)

        # Printed literally: the markup was never interpreted as HTML.
        assert squashed("<b>Bob</b> & Co") in text

    def test_renderer_cannot_fetch_any_url(self) -> None:
        from weasyprint.urls import URLFetcher

        fetcher = URLFetcher(allowed_protocols=())
        for url in ("file:///etc/passwd", "http://169.254.169.254/latest/meta-data/"):
            with pytest.raises(ValueError, match="disallowed protocol"):
                fetcher(url)


def test_document_dates_use_the_display_timezone() -> None:
    # 01:30 UTC on Sep 26 is still the evening of Sep 25 in New York. Printing
    # the UTC date would put tomorrow's date on an approval.
    from zoneinfo import ZoneInfo

    from app.services.pdf import format_date

    moment = datetime(2026, 9, 26, 1, 30, tzinfo=UTC)
    assert format_date(moment, ZoneInfo("America/New_York")) == "September 25, 2026"
    assert format_date(moment, ZoneInfo("UTC")) == "September 26, 2026"
