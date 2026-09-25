"""Tiny builders for valid rows, so each test only states what it cares about.

Each builder adds the object and flushes (sends the INSERT), so the returned
object has its id and any database errors surface immediately.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Client, Job, Organization, Quote, QuoteArea, TemplateItem, TradeTemplate
from app.models.enums import MeasureType


def make_org(session: Session, name: str = "Acme Painting") -> Organization:
    org = Organization(name=name, default_labor_rate_cents=6500, tax_rate=Decimal("0.05"))
    session.add(org)
    session.flush()
    return org


def make_client(session: Session, org: Organization, name: str = "Jane Homeowner") -> Client:
    client = Client(organization_id=org.id, name=name)
    session.add(client)
    session.flush()
    return client


def make_job(session: Session, org: Organization, client: Client | None = None) -> Job:
    client = client or make_client(session, org)
    job = Job(organization_id=org.id, client_id=client.id, title="Repaint living room")
    session.add(job)
    session.flush()
    return job


def make_quote(
    session: Session, org: Organization, job: Job | None = None, version: int = 1
) -> Quote:
    job = job or make_job(session, org)
    quote = Quote(organization_id=org.id, job_id=job.id, version=version)
    session.add(quote)
    session.flush()
    return quote


def make_area(
    session: Session, quote: Quote, template_item_id: uuid.UUID | None = None
) -> QuoteArea:
    area = QuoteArea(
        quote_id=quote.id,
        name="Living room walls",
        measure_type=MeasureType.AREA,
        quantity=Decimal("420"),
        template_item_id=template_item_id,
        coats=2,
    )
    session.add(area)
    session.flush()
    return area


def make_template_item(session: Session, org: Organization | None = None) -> TemplateItem:
    template = TradeTemplate(
        organization_id=org.id if org else None,
        trade="painting",
        name=f"Test template {uuid.uuid4().hex[:8]}",
    )
    item = TemplateItem(
        name="Walls",
        measure_type=MeasureType.AREA,
        material_name="Wall paint",
        material_unit="gallon",
        material_unit_cost_cents=4500,
        coverage_per_material_unit=Decimal("350"),
        waste_factor=Decimal("0.10"),
        labor_hours_per_unit=Decimal("0.006"),
        default_coats=2,
    )
    template.items.append(item)
    session.add(template)
    session.flush()
    return item


def utc_now() -> datetime:
    return datetime.now(UTC)
