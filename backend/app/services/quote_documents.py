"""What a client sees of a quote: the single definition used by both the PDF
and the public link page.

Keeping it in one place means the PDF and the public API can't disagree, and
it's easy to audit that nothing internal (ids, rate snapshots, overrides,
other versions) is exposed.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.models import Organization, Quote
from app.models.enums import LineItemKind, QuoteStatus


@dataclass(frozen=True)
class DocumentLine:
    description: str
    quantity: Decimal
    unit: str
    unit_price_cents: int
    total_cents: int


@dataclass(frozen=True)
class QuoteDocument:
    organization_name: str
    client_name: str
    job_title: str
    job_address: str | None
    version: int
    status: QuoteStatus
    lines: tuple[DocumentLine, ...]
    subtotal_cents: int
    tax_rate: Decimal
    tax_cents: int
    total_cents: int
    deposit_required_cents: int
    sent_at: datetime | None
    approved_at: datetime | None
    approved_by_name: str | None
    declined_at: datetime | None
    declined_by_name: str | None


def build_document(quote: Quote, organization: Organization) -> QuoteDocument:
    job = quote.job
    # Lines in reading order: by area (as added), material before labor.
    area_position = {area.id: area.position for area in quote.areas}
    kind_order = {LineItemKind.MATERIAL: 0, LineItemKind.LABOR: 1}
    lines = sorted(
        quote.line_items,
        key=lambda line: (
            area_position.get(line.area_id, -1) if line.area_id else -1,
            kind_order[line.kind],
        ),
    )
    return QuoteDocument(
        organization_name=organization.name,
        client_name=job.client.name,
        job_title=job.title,
        # The job's own address if set, else the client's.
        job_address=job.address or job.client.address,
        version=quote.version,
        status=quote.status,
        lines=tuple(
            DocumentLine(
                description=line.description,
                quantity=line.quantity,
                unit=line.unit,
                unit_price_cents=line.unit_price_cents,
                total_cents=line.total_cents,
            )
            for line in lines
        ),
        subtotal_cents=quote.subtotal_cents,
        tax_rate=quote.tax_rate,
        tax_cents=quote.tax_cents,
        total_cents=quote.total_cents,
        deposit_required_cents=quote.deposit_required_cents,
        sent_at=quote.sent_at,
        approved_at=quote.approved_at,
        approved_by_name=quote.approved_by_name,
        declined_at=quote.declined_at,
        declined_by_name=quote.declined_by_name,
    )
