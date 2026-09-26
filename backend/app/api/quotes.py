"""Quote endpoints: versions, areas, overrides.

Every endpoint that changes a quote returns the whole recalculated quote, so
a client (the quote builder UI) gets live totals from a single request.
"""

import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Response, status

from app.api.deps import AppSettings, CurrentTenant, DbSession
from app.schemas.quotes import (
    AreaCreate,
    AreaUpdate,
    OverrideRequest,
    QuoteOut,
    QuoteSummaryOut,
    QuoteUpdate,
    SendQuoteResponse,
    ShareLinkOut,
)
from app.services import pdf as pdf_service
from app.services import quotes as quote_service

router = APIRouter(tags=["quotes"])


# --- Versions --------------------------------------------------------------


@router.post("/jobs/{job_id}/quotes", response_model=QuoteOut, status_code=status.HTTP_201_CREATED)
def create_quote(job_id: uuid.UUID, tenant: CurrentTenant, session: DbSession) -> QuoteOut:
    """Create version 1 for a job. Later versions come from revisions."""
    return QuoteOut.from_quote(quote_service.create_first_quote(session, tenant, job_id))


@router.get("/jobs/{job_id}/quotes", response_model=list[QuoteSummaryOut])
def list_job_quotes(
    job_id: uuid.UUID, tenant: CurrentTenant, session: DbSession
) -> list[QuoteSummaryOut]:
    """All versions of a job's quote, oldest first."""
    return [
        QuoteSummaryOut.model_validate(quote)
        for quote in quote_service.list_job_quotes(session, tenant, job_id)
    ]


@router.get("/quotes/{quote_id}", response_model=QuoteOut)
def get_quote(quote_id: uuid.UUID, tenant: CurrentTenant, session: DbSession) -> QuoteOut:
    return QuoteOut.from_quote(quote_service.get_quote(session, tenant, quote_id))


@router.patch("/quotes/{quote_id}", response_model=QuoteOut)
def update_quote(
    quote_id: uuid.UUID, body: QuoteUpdate, tenant: CurrentTenant, session: DbSession
) -> QuoteOut:
    quote = quote_service.update_quote(
        session, tenant, quote_id, deposit_required_cents=body.deposit_required_cents
    )
    return QuoteOut.from_quote(quote)


@router.post(
    "/quotes/{quote_id}/revisions", response_model=QuoteOut, status_code=status.HTTP_201_CREATED
)
def create_revision(quote_id: uuid.UUID, tenant: CurrentTenant, session: DbSession) -> QuoteOut:
    """New draft version copying this (latest, non-draft) version."""
    return QuoteOut.from_quote(quote_service.create_revision(session, tenant, quote_id))


@router.post("/quotes/{quote_id}/refresh-rates", response_model=QuoteOut)
def refresh_rates(quote_id: uuid.UUID, tenant: CurrentTenant, session: DbSession) -> QuoteOut:
    """Pull current organization and template rates into this draft."""
    return QuoteOut.from_quote(quote_service.refresh_rates(session, tenant, quote_id))


# --- Areas -----------------------------------------------------------------


@router.post(
    "/quotes/{quote_id}/areas", response_model=QuoteOut, status_code=status.HTTP_201_CREATED
)
def add_area(
    quote_id: uuid.UUID, body: AreaCreate, tenant: CurrentTenant, session: DbSession
) -> QuoteOut:
    quote = quote_service.add_area(
        session,
        tenant,
        quote_id,
        template_item_id=body.template_item_id,
        name=body.name,
        quantity=body.quantity,
        coats=body.coats,
    )
    return QuoteOut.from_quote(quote)


@router.patch("/quotes/{quote_id}/areas/{area_id}", response_model=QuoteOut)
def update_area(
    quote_id: uuid.UUID,
    area_id: uuid.UUID,
    body: AreaUpdate,
    tenant: CurrentTenant,
    session: DbSession,
) -> QuoteOut:
    changes = body.model_dump(exclude_unset=True)
    return QuoteOut.from_quote(
        quote_service.update_area(session, tenant, quote_id, area_id, changes)
    )


@router.delete("/quotes/{quote_id}/areas/{area_id}", response_model=QuoteOut)
def delete_area(
    quote_id: uuid.UUID, area_id: uuid.UUID, tenant: CurrentTenant, session: DbSession
) -> QuoteOut:
    # Returns the updated quote (not 204) so the UI gets the new totals.
    return QuoteOut.from_quote(quote_service.delete_area(session, tenant, quote_id, area_id))


# --- Overrides -------------------------------------------------------------


@router.put("/quotes/{quote_id}/line-items/{line_id}/override", response_model=QuoteOut)
def set_override(
    quote_id: uuid.UUID,
    line_id: uuid.UUID,
    body: OverrideRequest,
    tenant: CurrentTenant,
    session: DbSession,
) -> QuoteOut:
    quote = quote_service.set_override(
        session,
        tenant,
        quote_id,
        line_id,
        quantity=body.quantity,
        unit_price_cents=body.unit_price_cents,
    )
    return QuoteOut.from_quote(quote)


@router.delete("/quotes/{quote_id}/line-items/{line_id}/override", response_model=QuoteOut)
def clear_override(
    quote_id: uuid.UUID, line_id: uuid.UUID, tenant: CurrentTenant, session: DbSession
) -> QuoteOut:
    return QuoteOut.from_quote(quote_service.clear_override(session, tenant, quote_id, line_id))


# --- Sending and PDFs --------------------------------------------------------


@router.post("/quotes/{quote_id}/send", response_model=SendQuoteResponse)
def send_quote(
    quote_id: uuid.UUID, tenant: CurrentTenant, session: DbSession, settings: AppSettings
) -> SendQuoteResponse:
    """Freeze the draft and create the client's link (shown this once)."""
    quote, link = quote_service.send_quote(
        session, tenant, quote_id, link_ttl=timedelta(days=settings.quote_link_ttl_days)
    )
    return SendQuoteResponse(
        quote=QuoteOut.from_quote(quote),
        link=ShareLinkOut(token=link.token, expires_at=link.expires_at),
    )


@router.post("/quotes/{quote_id}/share-link", response_model=ShareLinkOut)
def regenerate_link(
    quote_id: uuid.UUID, tenant: CurrentTenant, session: DbSession, settings: AppSettings
) -> ShareLinkOut:
    """A new client link for a sent quote. The previous link stops working."""
    link = quote_service.regenerate_link(
        session, tenant, quote_id, link_ttl=timedelta(days=settings.quote_link_ttl_days)
    )
    return ShareLinkOut(token=link.token, expires_at=link.expires_at)


def pdf_response(pdf: bytes, version: int) -> Response:
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            # inline: open in the browser's viewer; the filename is used on save.
            "Content-Disposition": f'inline; filename="quote-v{version}.pdf"',
            # Quotes are private: no shared caches.
            "Cache-Control": "private, no-store",
        },
    )


@router.get(
    "/quotes/{quote_id}/pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}, "description": "The quote as a PDF"}},
)
def quote_pdf(
    quote_id: uuid.UUID, tenant: CurrentTenant, session: DbSession, settings: AppSettings
) -> Response:
    document = quote_service.get_document(session, tenant, quote_id)
    pdf = pdf_service.render_quote_pdf(
        document, generated_at=datetime.now(UTC), timezone=ZoneInfo(settings.display_timezone)
    )
    return pdf_response(pdf, document.version)
