"""Shapes for the public (no-login) quote link endpoints.

Built only from QuoteDocument (services/quote_documents.py): what a client
may see. No ids, no rate snapshots, no override details, no other versions.
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.models.enums import QuoteStatus
from app.schemas.common import LongText
from app.services.public_quotes import PublicQuoteView

# A typed full name as the client's signature.
SignatureName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)
]


class PublicLineOut(BaseModel):
    description: str
    quantity: Decimal
    unit: str
    unit_price_cents: int
    total_cents: int


class PublicQuoteOut(BaseModel):
    organization_name: str
    client_name: str
    job_title: str
    job_address: str | None
    version: int
    status: QuoteStatus
    lines: list[PublicLineOut]
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
    link_expires_at: datetime
    is_latest_version: bool
    can_decide: bool

    @classmethod
    def from_view(cls, view: PublicQuoteView) -> "PublicQuoteOut":
        doc = view.document
        return cls(
            organization_name=doc.organization_name,
            client_name=doc.client_name,
            job_title=doc.job_title,
            job_address=doc.job_address,
            version=doc.version,
            status=doc.status,
            lines=[PublicLineOut(**line.__dict__) for line in doc.lines],
            subtotal_cents=doc.subtotal_cents,
            tax_rate=doc.tax_rate,
            tax_cents=doc.tax_cents,
            total_cents=doc.total_cents,
            deposit_required_cents=doc.deposit_required_cents,
            sent_at=doc.sent_at,
            approved_at=doc.approved_at,
            approved_by_name=doc.approved_by_name,
            declined_at=doc.declined_at,
            declined_by_name=doc.declined_by_name,
            link_expires_at=view.link_expires_at,
            is_latest_version=view.is_latest_version,
            can_decide=view.can_decide,
        )


class ApproveRequest(BaseModel):
    name: SignatureName
    # Must be literally true: approving requires ticking "I agree".
    accept_terms: Literal[True] = Field(description="The client ticked 'I agree'")


class DeclineRequest(BaseModel):
    name: SignatureName
    reason: LongText | None = None
