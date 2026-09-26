"""Public quote link endpoints: no login, the link token is the credential.

The token travels in the X-Quote-Token HEADER, not the URL: request paths are
written to access logs, and a token in a log line is a working approval link.

Every request here is rate-limited per client IP before anything else runs
(architecture rule 8), and decisions are additionally limited per link.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, Request, Response

from app.api.deps import AppSettings, DbSession
from app.api.quotes import pdf_response
from app.schemas.public import ApproveRequest, DeclineRequest, PublicQuoteOut
from app.security.links import hash_link_token
from app.services import pdf as pdf_service
from app.services import public_quotes, rate_limit

# Real tokens are 43 characters; bounds reject junk before any hashing.
QuoteToken = Annotated[str, Header(alias="X-Quote-Token", min_length=20, max_length=128)]


def _client_ip(request: Request) -> str:
    # Uvicorn replaces this with the X-Forwarded-For address when the request
    # comes from a trusted proxy (by default only 127.0.0.1, i.e. our Next.js
    # server in local dev; configure --forwarded-allow-ips in production).
    return request.client.host if request.client else "unknown"


def limit_by_ip(request: Request, session: DbSession, settings: AppSettings) -> None:
    rate_limit.check(
        session,
        key=f"public-ip:{_client_ip(request)}",
        limit=settings.public_requests_per_minute,
        window=timedelta(minutes=1),
    )


def limit_decisions(token: QuoteToken, session: DbSession, settings: AppSettings) -> None:
    # Per link: nobody gets unlimited approve/decline attempts on one quote.
    rate_limit.check(
        session,
        key=f"quote-decision:{hash_link_token(token)}",
        limit=settings.quote_decisions_per_hour,
        window=timedelta(hours=1),
    )


def _no_index(response: Response) -> None:
    # Private data behind a secret link: never cache or index it.
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Robots-Tag"] = "noindex"


router = APIRouter(prefix="/public", tags=["public"], dependencies=[Depends(limit_by_ip)])


@router.get("/quote", response_model=PublicQuoteOut)
def view_quote(token: QuoteToken, session: DbSession, response: Response) -> PublicQuoteOut:
    _no_index(response)
    return PublicQuoteOut.from_view(public_quotes.view_quote(session, token))


@router.get(
    "/quote/pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}, "description": "The quote as a PDF"}},
)
def quote_pdf(token: QuoteToken, session: DbSession, settings: AppSettings) -> Response:
    document = public_quotes.document_for(session, token)
    pdf = pdf_service.render_quote_pdf(
        document, generated_at=datetime.now(UTC), timezone=ZoneInfo(settings.display_timezone)
    )
    return pdf_response(pdf, document.version)


@router.post(
    "/quote/approve", response_model=PublicQuoteOut, dependencies=[Depends(limit_decisions)]
)
def approve(
    token: QuoteToken, body: ApproveRequest, session: DbSession, response: Response
) -> PublicQuoteOut:
    _no_index(response)
    return PublicQuoteOut.from_view(public_quotes.approve(session, token, name=body.name))


@router.post(
    "/quote/decline", response_model=PublicQuoteOut, dependencies=[Depends(limit_decisions)]
)
def decline(
    token: QuoteToken, body: DeclineRequest, session: DbSession, response: Response
) -> PublicQuoteOut:
    _no_index(response)
    view = public_quotes.decline(session, token, name=body.name, reason=body.reason)
    return PublicQuoteOut.from_view(view)
