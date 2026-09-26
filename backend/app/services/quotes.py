"""Quotes: versions, measured areas, overrides, and recalculation.

Rules implemented here:
- Only DRAFT quotes can be edited. A sent/approved/declined quote is changed
  by creating a revision: a new draft version on the same job (rule 7).
- Every change recalculates the quote in the same transaction, so stored
  line items and totals always match the areas ("live totals").
- Recalculation uses only the quote's own rate snapshots (rule 6), via the
  pure estimating engine.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import psycopg
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.estimating import (
    AreaInput,
    EstimateInput,
    ItemRates,
    LineKind,
    LineOverride,
    calculate_estimate,
)
from app.models import Organization, Quote, QuoteArea, QuoteLineItem, TemplateItem
from app.models.enums import LineItemKind, QuoteStatus
from app.repositories.organizations import OrganizationRepository
from app.repositories.quotes import QuoteRepository
from app.repositories.templates import TemplateRepository
from app.security.links import hash_link_token, new_link_token
from app.services import jobs as job_service
from app.services.context import Tenant
from app.services.errors import ConflictError, InvalidInputError, NotFoundError
from app.services.quote_documents import QuoteDocument, build_document

_UNIQUE_VERSION_CONSTRAINT = "uq_quotes_job_id_version"

# The template item fields copied onto an area (its rate snapshot).
_RATE_FIELDS = (
    "material_name",
    "material_unit",
    "material_unit_cost_cents",
    "coverage_per_material_unit",
    "waste_factor",
    "labor_hours_per_unit",
)


# ---------------------------------------------------------------------------
# Lookups and guards
# ---------------------------------------------------------------------------


def _repo(session: Session, tenant: Tenant) -> QuoteRepository:
    return QuoteRepository(session, tenant.organization_id)


def get_quote(session: Session, tenant: Tenant, quote_id: uuid.UUID) -> Quote:
    quote = _repo(session, tenant).get_with_details(quote_id)
    if quote is None:
        raise NotFoundError("Quote")
    return quote


def _get_draft(session: Session, tenant: Tenant, quote_id: uuid.UUID) -> Quote:
    quote = get_quote(session, tenant, quote_id)
    if quote.status is not QuoteStatus.DRAFT:
        raise ConflictError(
            f"This quote is {quote.status} and can't be edited; create a revision instead"
        )
    return quote


def _find_area(quote: Quote, area_id: uuid.UUID) -> QuoteArea:
    # Searching the quote's own areas means an area id from another quote
    # (or another org) is simply "not found".
    area = next((area for area in quote.areas if area.id == area_id), None)
    if area is None:
        raise NotFoundError("Area")
    return area


def _find_line(quote: Quote, line_id: uuid.UUID) -> QuoteLineItem:
    line = next((line for line in quote.line_items if line.id == line_id), None)
    if line is None:
        raise NotFoundError("Line item")
    return line


def _visible_template_item(session: Session, tenant: Tenant, item_id: uuid.UUID) -> TemplateItem:
    item = TemplateRepository(session, tenant.organization_id).get_visible_item(item_id)
    if item is None:
        raise NotFoundError("Template item")
    return item


def _copy_rates(item: TemplateItem, area: QuoteArea) -> None:
    for field in _RATE_FIELDS:
        setattr(area, field, getattr(item, field))


# ---------------------------------------------------------------------------
# Recalculation: the bridge between stored data and the pure engine
# ---------------------------------------------------------------------------


def _area_input(area: QuoteArea) -> AreaInput:
    return AreaInput(
        area_id=area.id,
        name=area.name,
        quantity=area.quantity,
        coats=area.coats,
        rates=ItemRates(
            material_name=area.material_name,
            material_unit=area.material_unit,
            material_unit_cost_cents=area.material_unit_cost_cents,
            coverage_per_material_unit=area.coverage_per_material_unit,
            waste_factor=area.waste_factor,
            labor_hours_per_unit=area.labor_hours_per_unit,
        ),
    )


def _override_input(line: QuoteLineItem) -> LineOverride:
    assert line.area_id is not None
    return LineOverride(
        area_id=line.area_id,
        kind=LineKind(line.kind.value),
        quantity=line.override_quantity,
        unit_price_cents=line.override_unit_price_cents,
    )


def _recalculate(quote: Quote) -> None:
    """Re-price the quote from its own data and store the results.

    Line items are updated IN PLACE, matched by (area_id, kind), so their ids
    stay stable across recalculations (the override endpoints rely on that).
    """
    estimate = calculate_estimate(
        EstimateInput(
            areas=tuple(_area_input(area) for area in quote.areas),
            labor_rate_cents=quote.labor_rate_cents,
            tax_rate=quote.tax_rate,
            overrides=tuple(
                _override_input(line)
                for line in quote.line_items
                if line.is_override and line.area_id is not None
            ),
        )
    )

    existing = {(line.area_id, line.kind): line for line in quote.line_items}
    calculated_keys: set[tuple[uuid.UUID | None, LineItemKind]] = set()
    for calculated in estimate.lines:
        key = (calculated.area_id, LineItemKind(calculated.kind.value))
        calculated_keys.add(key)
        line = existing.get(key)
        if line is None:
            line = QuoteLineItem(area_id=calculated.area_id, kind=key[1], is_override=False)
            quote.line_items.append(line)
        line.description = calculated.description
        line.quantity = calculated.quantity
        line.unit = calculated.unit
        line.unit_price_cents = calculated.unit_price_cents
        line.total_cents = calculated.total_cents

    # Lines whose area no longer exists.
    for existing_key, stale_line in existing.items():
        if existing_key not in calculated_keys:
            quote.line_items.remove(stale_line)

    quote.subtotal_cents = estimate.subtotal_cents
    quote.tax_cents = estimate.tax_cents
    quote.total_cents = estimate.total_cents
    # Placeholder rule (pending KBS): a deposit can never exceed the total,
    # so if the total drops below it, the deposit drops with it.
    quote.deposit_required_cents = min(quote.deposit_required_cents, quote.total_cents)


def _save(session: Session, quote: Quote) -> Quote:
    """Flush pending changes (giving new rows their ids), recalculate, commit."""
    session.flush()
    _recalculate(quote)
    session.commit()
    return quote


# ---------------------------------------------------------------------------
# Quotes and versions
# ---------------------------------------------------------------------------


def list_job_quotes(session: Session, tenant: Tenant, job_id: uuid.UUID) -> list[Quote]:
    job_service.get_job(session, tenant, job_id)  # 404 for unknown/other-org jobs
    return list(_repo(session, tenant).list_for_job(job_id))


def _add_version(session: Session, tenant: Tenant, quote: Quote) -> Quote:
    """Insert a new quote version, turning a version-number race into a 409."""
    try:
        return _repo(session, tenant).add(quote)
    except IntegrityError as error:
        # Two requests creating the next version at the same moment: the
        # UNIQUE (job_id, version) constraint lets only one win.
        session.rollback()
        original = error.orig
        if (
            isinstance(original, psycopg.Error)
            and original.diag.constraint_name == _UNIQUE_VERSION_CONSTRAINT
        ):
            raise ConflictError("Another version was just created; reload and try again") from error
        raise


def create_first_quote(session: Session, tenant: Tenant, job_id: uuid.UUID) -> Quote:
    job_service.get_job(session, tenant, job_id)
    if _repo(session, tenant).latest_for_job(job_id) is not None:
        raise ConflictError("This job already has a quote; create a revision of the latest version")

    organization = OrganizationRepository(session).get(tenant.organization_id)
    assert organization is not None
    quote = _add_version(
        session,
        tenant,
        Quote(
            job_id=job_id,
            version=1,
            # Rate snapshots: later changes to org settings don't affect it.
            labor_rate_cents=organization.default_labor_rate_cents,
            tax_rate=organization.tax_rate,
        ),
    )
    return _save(session, quote)


def create_revision(session: Session, tenant: Tenant, quote_id: uuid.UUID) -> Quote:
    """New draft version copying the source's areas, snapshots, and overrides."""
    source = get_quote(session, tenant, quote_id)
    latest = _repo(session, tenant).latest_for_job(source.job_id)
    if latest is None or latest.id != source.id:
        raise ConflictError("Only the latest version of a quote can be revised")
    if source.status is QuoteStatus.DRAFT:
        raise ConflictError("The latest version is still a draft; edit it instead")

    revision = _add_version(
        session,
        tenant,
        Quote(
            job_id=source.job_id,
            version=source.version + 1,
            labor_rate_cents=source.labor_rate_cents,
            tax_rate=source.tax_rate,
            # The deposit is copied only at the end: until the revision is
            # priced its total is 0, and the database refuses a deposit
            # larger than the total.
        ),
    )

    new_area_ids: dict[uuid.UUID, uuid.UUID] = {}
    for area in source.areas:
        copy = QuoteArea(
            position=area.position,
            name=area.name,
            measure_type=area.measure_type,
            quantity=area.quantity,
            coats=area.coats,
            template_item_id=area.template_item_id,
        )
        for field in _RATE_FIELDS:
            setattr(copy, field, getattr(area, field))
        revision.areas.append(copy)
        session.flush()  # assigns copy.id
        new_area_ids[area.id] = copy.id

    # Build the new lines, then carry the source's overrides over to them.
    session.flush()
    _recalculate(revision)
    session.flush()
    new_lines = {(line.area_id, line.kind): line for line in revision.line_items}
    for line in source.line_items:
        if line.is_override and line.area_id is not None:
            target = new_lines[(new_area_ids[line.area_id], line.kind)]
            target.override_quantity = line.override_quantity
            target.override_unit_price_cents = line.override_unit_price_cents
            target.is_override = True

    session.flush()
    _recalculate(revision)  # now with the overrides applied
    revision.deposit_required_cents = min(source.deposit_required_cents, revision.total_cents)
    session.commit()
    return revision


def update_quote(
    session: Session, tenant: Tenant, quote_id: uuid.UUID, *, deposit_required_cents: int
) -> Quote:
    quote = _get_draft(session, tenant, quote_id)
    if deposit_required_cents > quote.total_cents:
        raise InvalidInputError("Deposit can't be more than the quote total")
    quote.deposit_required_cents = deposit_required_cents
    return _save(session, quote)


def refresh_rates(session: Session, tenant: Tenant, quote_id: uuid.UUID) -> Quote:
    """Pull the organization's and templates' CURRENT rates into a draft.

    The one deliberate way for new prices to reach an existing quote. Areas
    whose template item was deleted keep their snapshot.
    """
    quote = _get_draft(session, tenant, quote_id)
    organization = OrganizationRepository(session).get(tenant.organization_id)
    assert organization is not None
    quote.labor_rate_cents = organization.default_labor_rate_cents
    quote.tax_rate = organization.tax_rate

    templates = TemplateRepository(session, tenant.organization_id)
    for area in quote.areas:
        if area.template_item_id is None:
            continue
        item = templates.get_visible_item(area.template_item_id)
        if item is not None:
            _copy_rates(item, area)
    return _save(session, quote)


# ---------------------------------------------------------------------------
# Areas
# ---------------------------------------------------------------------------


def add_area(
    session: Session,
    tenant: Tenant,
    quote_id: uuid.UUID,
    *,
    template_item_id: uuid.UUID,
    name: str,
    quantity: Decimal,
    coats: int | None,
) -> Quote:
    quote = _get_draft(session, tenant, quote_id)
    # Only system items or this org's own: never another org's template.
    item = _visible_template_item(session, tenant, template_item_id)
    area = QuoteArea(
        # After the current last area. Deleting areas leaves gaps; only the
        # order matters.
        position=max((existing.position for existing in quote.areas), default=-1) + 1,
        name=name,
        measure_type=item.measure_type,
        quantity=quantity,
        coats=coats if coats is not None else item.default_coats,
        template_item_id=item.id,
    )
    _copy_rates(item, area)
    quote.areas.append(area)
    return _save(session, quote)


def update_area(
    session: Session,
    tenant: Tenant,
    quote_id: uuid.UUID,
    area_id: uuid.UUID,
    changes: dict[str, Any],
) -> Quote:
    quote = _get_draft(session, tenant, quote_id)
    area = _find_area(quote, area_id)
    for field, value in changes.items():
        setattr(area, field, value)
    return _save(session, quote)


def delete_area(session: Session, tenant: Tenant, quote_id: uuid.UUID, area_id: uuid.UUID) -> Quote:
    quote = _get_draft(session, tenant, quote_id)
    area = _find_area(quote, area_id)
    # Delete the area's lines ourselves, and FLUSH before deleting the area.
    # SQLAlchemy has no relationship between lines and areas, so it doesn't
    # know the lines must go first; if the area went first, the database's
    # ON DELETE CASCADE would remove the lines behind SQLAlchemy's back and
    # its own DELETEs would then find nothing to delete.
    for line in [line for line in quote.line_items if line.area_id == area.id]:
        quote.line_items.remove(line)
    session.flush()
    quote.areas.remove(area)
    return _save(session, quote)


# ---------------------------------------------------------------------------
# Overrides
# ---------------------------------------------------------------------------


def set_override(
    session: Session,
    tenant: Tenant,
    quote_id: uuid.UUID,
    line_id: uuid.UUID,
    *,
    quantity: Decimal | None,
    unit_price_cents: int | None,
) -> Quote:
    """Replace the line's override (PUT semantics: unset fields are cleared)."""
    quote = _get_draft(session, tenant, quote_id)
    line = _find_line(quote, line_id)
    assert line.area_id is not None
    try:
        # The engine's own validation (e.g. at most 3 decimal places).
        LineOverride(
            area_id=line.area_id,
            kind=LineKind(line.kind.value),
            quantity=quantity,
            unit_price_cents=unit_price_cents,
        )
    except ValueError as error:
        raise InvalidInputError(str(error)) from error

    line.override_quantity = quantity
    line.override_unit_price_cents = unit_price_cents
    line.is_override = True
    return _save(session, quote)


def clear_override(
    session: Session, tenant: Tenant, quote_id: uuid.UUID, line_id: uuid.UUID
) -> Quote:
    quote = _get_draft(session, tenant, quote_id)
    line = _find_line(quote, line_id)
    line.override_quantity = None
    line.override_unit_price_cents = None
    line.is_override = False
    return _save(session, quote)


# ---------------------------------------------------------------------------
# Sending, share links, and documents (Milestone 6)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IssuedLink:
    """The raw token exists only in this return value: it's shown to the
    contractor once and never stored (only its hash is)."""

    token: str
    expires_at: datetime


def _issue_link(quote: Quote, ttl: timedelta) -> IssuedLink:
    token = new_link_token()
    expires_at = datetime.now(UTC) + ttl
    # Replacing the hash also invalidates any previous link for this quote.
    quote.public_token_hash = hash_link_token(token)
    quote.token_expires_at = expires_at
    return IssuedLink(token=token, expires_at=expires_at)


def _require_latest(session: Session, tenant: Tenant, quote: Quote) -> None:
    latest = _repo(session, tenant).latest_for_job(quote.job_id)
    if latest is None or latest.id != quote.id:
        raise ConflictError("This quote has been replaced by a newer version")


def send_quote(
    session: Session, tenant: Tenant, quote_id: uuid.UUID, *, link_ttl: timedelta
) -> tuple[Quote, IssuedLink]:
    """Draft -> sent: freeze the quote and create its client link."""
    quote = _get_draft(session, tenant, quote_id)
    if not quote.areas:
        raise ConflictError("Add at least one area before sending")
    quote.status = QuoteStatus.SENT
    quote.sent_at = datetime.now(UTC)
    link = _issue_link(quote, link_ttl)
    session.commit()
    return quote, link


def regenerate_link(
    session: Session, tenant: Tenant, quote_id: uuid.UUID, *, link_ttl: timedelta
) -> IssuedLink:
    """A fresh link for a sent quote (e.g. the old one was lost or expired).
    Only the hash is stored, so the old link can't be shown again; making a
    new one invalidates it."""
    quote = get_quote(session, tenant, quote_id)
    if quote.status is not QuoteStatus.SENT:
        raise ConflictError(f"Only sent quotes have client links (this one is {quote.status})")
    _require_latest(session, tenant, quote)
    link = _issue_link(quote, link_ttl)
    session.commit()
    return link


def get_document(session: Session, tenant: Tenant, quote_id: uuid.UUID) -> QuoteDocument:
    """The client-facing view of one of the contractor's own quotes (for PDFs)."""
    quote = get_quote(session, tenant, quote_id)
    organization = session.get(Organization, tenant.organization_id)
    assert organization is not None
    return build_document(quote, organization)
