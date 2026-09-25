"""The database's own rules: the "second line of defense" from CLAUDE.md.

Services (later milestones) will validate input first, but these tests prove
that even buggy application code can't store invalid or cross-tenant data.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from decimal import Decimal
from typing import Any

import psycopg
import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Client,
    Job,
    Organization,
    Payment,
    Quote,
    QuoteArea,
    QuoteLineItem,
    TemplateItem,
    TradeTemplate,
    User,
)
from app.models.enums import LineItemKind, PaymentKind, QuoteStatus, UserRole
from tests.factories import (
    make_area,
    make_client,
    make_job,
    make_org,
    make_quote,
    make_template_item,
    utc_now,
)


@contextmanager
def expect_violation(session: Session, constraint: str) -> Iterator[None]:
    """Assert the block fails because of one *specific* named constraint.

    Checking the name (not just "some IntegrityError") stops a test from
    passing for the wrong reason, e.g. a NOT NULL error masking a missing CHECK.
    """
    with pytest.raises(IntegrityError) as excinfo:
        yield
        session.flush()
    original = excinfo.value.orig
    assert isinstance(original, psycopg.Error)
    assert original.diag.constraint_name == constraint


# Rate snapshots every quote needs (Milestone 4).
_RATES: dict[str, Any] = {"labor_rate_cents": 6500, "tax_rate": Decimal("0.05")}


def _line_item(quote: Quote, **overrides: object) -> QuoteLineItem:
    fields: dict[str, object] = {
        "quote_id": quote.id,
        "kind": LineItemKind.MATERIAL,
        "description": "Wall paint",
        "quantity": Decimal("3"),
        "unit": "gallon",
        "unit_price_cents": 4500,
        "total_cents": 13500,
    } | overrides
    return QuoteLineItem(**fields)


# ---------------------------------------------------------------------------
# Multi-tenancy: composite foreign keys (design choice 1)
# ---------------------------------------------------------------------------


class TestCrossTenantReferences:
    def test_job_cannot_reference_another_orgs_client(self, db_session: Session) -> None:
        org_a, org_b = make_org(db_session, "A"), make_org(db_session, "B")
        client_of_b = make_client(db_session, org_b)

        with expect_violation(db_session, "fk_jobs_organization_id_client_id_clients"):
            db_session.add(Job(organization_id=org_a.id, client_id=client_of_b.id, title="x"))

    def test_quote_cannot_reference_another_orgs_job(self, db_session: Session) -> None:
        org_a, org_b = make_org(db_session, "A"), make_org(db_session, "B")
        job_of_b = make_job(db_session, org_b)

        with expect_violation(db_session, "fk_quotes_organization_id_job_id_jobs"):
            db_session.add(Quote(organization_id=org_a.id, job_id=job_of_b.id, version=1, **_RATES))

    def test_payment_cannot_reference_another_orgs_job(self, db_session: Session) -> None:
        org_a, org_b = make_org(db_session, "A"), make_org(db_session, "B")
        job_of_b = make_job(db_session, org_b)

        with expect_violation(db_session, "fk_payments_organization_id_job_id_jobs"):
            db_session.add(
                Payment(
                    organization_id=org_a.id,
                    job_id=job_of_b.id,
                    amount_cents=10_000,
                    kind=PaymentKind.DEPOSIT,
                    received_at=utc_now(),
                )
            )

    def test_line_item_cannot_reference_an_area_on_another_quote(self, db_session: Session) -> None:
        org = make_org(db_session)
        quote_1 = make_quote(db_session, org)
        quote_2 = make_quote(db_session, org)
        area_on_quote_2 = make_area(db_session, quote_2)

        with expect_violation(db_session, "fk_quote_line_items_quote_id_area_id_quote_areas"):
            db_session.add(_line_item(quote_1, area_id=area_on_quote_2.id))

    def test_same_org_references_are_allowed(self, db_session: Session) -> None:
        org = make_org(db_session)
        quote = make_quote(db_session, org)
        area = make_area(db_session, quote)
        db_session.add(_line_item(quote, area_id=area.id))
        db_session.flush()  # no error


# ---------------------------------------------------------------------------
# Quotes
# ---------------------------------------------------------------------------


class TestQuoteRules:
    def test_version_is_unique_per_job(self, db_session: Session) -> None:
        org = make_org(db_session)
        job = make_job(db_session, org)
        make_quote(db_session, org, job, version=1)

        with expect_violation(db_session, "uq_quotes_job_id_version"):
            db_session.add(Quote(organization_id=org.id, job_id=job.id, version=1, **_RATES))

    def test_same_version_number_on_different_jobs_is_fine(self, db_session: Session) -> None:
        org = make_org(db_session)
        make_quote(db_session, org, version=1)
        make_quote(db_session, org, version=1)  # different job: no error

    def test_total_must_equal_subtotal_plus_tax(self, db_session: Session) -> None:
        quote = make_quote(db_session, make_org(db_session))

        with expect_violation(db_session, "ck_quotes_total_is_sum"):
            quote.subtotal_cents, quote.tax_cents, quote.total_cents = 10_000, 500, 10_499

    def test_deposit_cannot_exceed_total(self, db_session: Session) -> None:
        quote = make_quote(db_session, make_org(db_session))

        with expect_violation(db_session, "ck_quotes_deposit_within_total"):
            quote.deposit_required_cents = 1

    def test_approved_quote_must_record_who_and_when(self, db_session: Session) -> None:
        quote = make_quote(db_session, make_org(db_session))

        with expect_violation(db_session, "ck_quotes_approval_recorded"):
            quote.status = QuoteStatus.APPROVED

    def test_approved_quote_with_approval_details_is_valid(self, db_session: Session) -> None:
        quote = make_quote(db_session, make_org(db_session))
        quote.status = QuoteStatus.APPROVED
        quote.approved_at = utc_now()
        quote.approved_by_name = "Jane Homeowner"
        db_session.flush()  # no error

    def test_token_hash_requires_expiry(self, db_session: Session) -> None:
        quote = make_quote(db_session, make_org(db_session))

        with expect_violation(db_session, "ck_quotes_token_hash_and_expiry_together"):
            quote.public_token_hash = "a" * 64

    def test_token_hash_is_unique(self, db_session: Session) -> None:
        org = make_org(db_session)
        expires = utc_now() + timedelta(days=30)
        first = make_quote(db_session, org)
        first.public_token_hash, first.token_expires_at = "a" * 64, expires
        db_session.flush()
        second = make_quote(db_session, org)

        with expect_violation(db_session, "uq_quotes_public_token_hash"):
            second.public_token_hash, second.token_expires_at = "a" * 64, expires

    def test_status_rejects_unknown_values(self, db_session: Session) -> None:
        # Raw SQL bypasses the Python enum, proving the database itself checks.
        quote = make_quote(db_session, make_org(db_session))

        with expect_violation(db_session, "ck_quotes_quote_status"):
            db_session.execute(
                text("UPDATE quotes SET status = 'bogus' WHERE id = :id"), {"id": quote.id}
            )


# ---------------------------------------------------------------------------
# Value checks on other tables (one representative case per constraint)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("column", "bad_value", "constraint"),
    [
        ("default_labor_rate_cents", -1, "ck_organizations_labor_rate_non_negative"),
        ("tax_rate", Decimal("1.5"), "ck_organizations_tax_rate_range"),
        ("tax_rate", Decimal("-0.01"), "ck_organizations_tax_rate_range"),
    ],
)
def test_organization_value_checks(
    db_session: Session, column: str, bad_value: object, constraint: str
) -> None:
    org = make_org(db_session)
    with expect_violation(db_session, constraint):
        setattr(org, column, bad_value)


@pytest.mark.parametrize(
    ("column", "bad_value", "constraint"),
    [
        ("coverage_per_material_unit", Decimal("0"), "ck_template_items_coverage_positive"),
        ("waste_factor", Decimal("-0.1"), "ck_template_items_waste_non_negative"),
        ("labor_hours_per_unit", Decimal("-1"), "ck_template_items_labor_non_negative"),
        ("default_coats", 0, "ck_template_items_default_coats_positive"),
        ("material_unit_cost_cents", -1, "ck_template_items_material_cost_non_negative"),
    ],
)
def test_template_item_value_checks(
    db_session: Session, column: str, bad_value: object, constraint: str
) -> None:
    item = make_template_item(db_session)
    with expect_violation(db_session, constraint):
        setattr(item, column, bad_value)


@pytest.mark.parametrize(
    ("column", "bad_value", "constraint"),
    [
        ("coats", 0, "ck_quote_areas_coats_positive"),
        ("quantity", Decimal("-1"), "ck_quote_areas_quantity_non_negative"),
    ],
)
def test_quote_area_value_checks(
    db_session: Session, column: str, bad_value: object, constraint: str
) -> None:
    area = make_area(db_session, make_quote(db_session, make_org(db_session)))
    with expect_violation(db_session, constraint):
        setattr(area, column, bad_value)


def test_line_item_amounts_cannot_be_negative(db_session: Session) -> None:
    quote = make_quote(db_session, make_org(db_session))
    with expect_violation(db_session, "ck_quote_line_items_amounts_non_negative"):
        db_session.add(_line_item(quote, total_cents=-1))


def test_payment_amount_must_be_positive(db_session: Session) -> None:
    org = make_org(db_session)
    job = make_job(db_session, org)
    with expect_violation(db_session, "ck_payments_amount_positive"):
        db_session.add(
            Payment(
                organization_id=org.id,
                job_id=job.id,
                amount_cents=0,
                kind=PaymentKind.FINAL,
                received_at=utc_now(),
            )
        )


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


# Any non-empty value satisfies the column; these tests are about emails.
_HASH = "$argon2id$placeholder"


class TestUsers:
    def test_email_is_unique_across_all_orgs(self, db_session: Session) -> None:
        org_a, org_b = make_org(db_session, "A"), make_org(db_session, "B")
        db_session.add(
            User(
                organization_id=org_a.id,
                email="bob@x.com",
                role=UserRole.OWNER,
                password_hash=_HASH,
            )
        )
        db_session.flush()

        with expect_violation(db_session, "uq_users_email"):
            db_session.add(
                User(
                    organization_id=org_b.id,
                    email="bob@x.com",
                    role=UserRole.OWNER,
                    password_hash=_HASH,
                )
            )

    def test_email_must_be_stored_lowercase(self, db_session: Session) -> None:
        org = make_org(db_session)
        with expect_violation(db_session, "ck_users_email_lowercase"):
            db_session.add(
                User(
                    organization_id=org.id,
                    email="Bob@x.com",
                    role=UserRole.STAFF,
                    password_hash=_HASH,
                )
            )


# ---------------------------------------------------------------------------
# Trade templates
# ---------------------------------------------------------------------------


def test_system_template_names_are_unique_despite_null_org(db_session: Session) -> None:
    # Without NULLS NOT DISTINCT, two rows with organization_id = NULL would
    # never be considered duplicates.
    db_session.add(TradeTemplate(organization_id=None, trade="painting", name="Same"))
    db_session.flush()

    with expect_violation(db_session, "uq_trade_templates_organization_id_trade_name"):
        db_session.add(TradeTemplate(organization_id=None, trade="painting", name="Same"))


# ---------------------------------------------------------------------------
# Delete behavior (ON DELETE rules)
# ---------------------------------------------------------------------------


def _count(session: Session, model: type[object]) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


class TestDeleteBehavior:
    def test_deleting_a_quote_deletes_its_areas_and_line_items(self, db_session: Session) -> None:
        quote = make_quote(db_session, make_org(db_session))
        area = make_area(db_session, quote)
        db_session.add(_line_item(quote, area_id=area.id))
        db_session.add(_line_item(quote))  # quote-level line (no area)
        db_session.flush()

        # A bulk SQL DELETE, so this tests the *database's* ON DELETE CASCADE,
        # not SQLAlchemy's ORM-side cascade.
        db_session.execute(delete(Quote).where(Quote.id == quote.id))
        db_session.expire_all()

        assert _count(db_session, QuoteArea) == 0
        assert _count(db_session, QuoteLineItem) == 0

    def test_deleting_a_template_item_keeps_quote_areas(self, db_session: Session) -> None:
        org = make_org(db_session)
        item = make_template_item(db_session, org)
        area = make_area(db_session, make_quote(db_session, org), template_item_id=item.id)

        db_session.execute(delete(TemplateItem).where(TemplateItem.id == item.id))
        db_session.expire_all()

        # The area survives; only its link to the template is cleared.
        reloaded = db_session.get(QuoteArea, area.id)
        assert reloaded is not None
        assert reloaded.template_item_id is None

    def test_cannot_delete_a_client_that_has_jobs(self, db_session: Session) -> None:
        org = make_org(db_session)
        client = make_client(db_session, org)
        make_job(db_session, org, client)

        with expect_violation(db_session, "fk_jobs_organization_id_client_id_clients"):
            db_session.execute(delete(Client).where(Client.id == client.id))

    def test_cannot_delete_an_org_that_owns_data(self, db_session: Session) -> None:
        org = make_org(db_session)
        make_client(db_session, org)

        with expect_violation(db_session, "fk_clients_organization_id_organizations"):
            db_session.execute(delete(Organization).where(Organization.id == org.id))


# ---------------------------------------------------------------------------
# Exact decimals (architecture rule 3: no floats)
# ---------------------------------------------------------------------------


def test_numeric_columns_round_trip_as_exact_decimals(db_session: Session) -> None:
    org = make_org(db_session)
    org.tax_rate = Decimal("0.04712")
    db_session.flush()
    db_session.expire_all()  # force a real re-read from the database

    reloaded = db_session.get(Organization, org.id)
    assert reloaded is not None
    assert isinstance(reloaded.tax_rate, Decimal)
    assert reloaded.tax_rate == Decimal("0.04712")
