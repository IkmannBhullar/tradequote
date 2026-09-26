"""What a client can do with a quote link: view it, and approve or decline.

The token is the only credential. Every entry point hashes it, finds exactly
one quote, and checks the link hasn't expired. Decisions additionally require
the quote to still be "sent" and to be the job's latest version.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import Organization, Quote
from app.models.enums import JobStatus, QuoteStatus
from app.repositories.jobs import JobRepository
from app.repositories.public_quotes import PublicQuoteRepository
from app.repositories.quotes import QuoteRepository
from app.security.links import hash_link_token
from app.services.errors import ConflictError, GoneError, NotFoundError
from app.services.quote_documents import QuoteDocument, build_document


@dataclass(frozen=True)
class PublicQuoteView:
    document: QuoteDocument
    link_expires_at: datetime
    # False once a newer version exists: the client must use the new link.
    is_latest_version: bool
    can_decide: bool


def _find(session: Session, token: str, *, lock: bool = False) -> Quote:
    quote = PublicQuoteRepository(session).get_by_token_hash(hash_link_token(token), lock=lock)
    if quote is None:
        # Same answer for "never existed" and "replaced by a newer link".
        raise NotFoundError("Quote")
    assert quote.token_expires_at is not None  # guaranteed by a CHECK constraint
    if quote.token_expires_at <= datetime.now(UTC):
        raise GoneError("This link has expired. Ask your contractor for a new one.")
    return quote


def _is_latest(session: Session, quote: Quote) -> bool:
    # Scoped to the quote's own organization, which the token identified.
    latest = QuoteRepository(session, quote.organization_id).latest_for_job(quote.job_id)
    return latest is not None and latest.id == quote.id


def _organization(session: Session, quote: Quote) -> Organization:
    organization = session.get(Organization, quote.organization_id)
    assert organization is not None
    return organization


def view_quote(session: Session, token: str) -> PublicQuoteView:
    quote = _find(session, token)
    is_latest = _is_latest(session, quote)
    assert quote.token_expires_at is not None
    return PublicQuoteView(
        document=build_document(quote, _organization(session, quote)),
        link_expires_at=quote.token_expires_at,
        is_latest_version=is_latest,
        can_decide=is_latest and quote.status is QuoteStatus.SENT,
    )


def document_for(session: Session, token: str) -> QuoteDocument:
    quote = _find(session, token)
    return build_document(quote, _organization(session, quote))


def _decidable(session: Session, token: str) -> Quote:
    # lock=True: concurrent decisions on the same quote run one at a time.
    quote = _find(session, token, lock=True)
    if quote.status is not QuoteStatus.SENT:
        raise ConflictError(f"This quote has already been {quote.status}")
    if not _is_latest(session, quote):
        raise ConflictError("This quote has been replaced by a newer version")
    return quote


def approve(session: Session, token: str, *, name: str) -> PublicQuoteView:
    quote = _decidable(session, token)
    quote.status = QuoteStatus.APPROVED
    quote.approved_at = datetime.now(UTC)
    quote.approved_by_name = name

    # The job moves forward on the contractor's board.
    job = JobRepository(session, quote.organization_id).get(quote.job_id)
    assert job is not None
    if job.status is JobStatus.QUOTED:
        job.status = JobStatus.APPROVED
    session.commit()
    return view_quote(session, token)


def decline(session: Session, token: str, *, name: str, reason: str | None) -> PublicQuoteView:
    quote = _decidable(session, token)
    quote.status = QuoteStatus.DECLINED
    quote.declined_at = datetime.now(UTC)
    quote.declined_by_name = name
    quote.decline_reason = reason
    # The job stays "quoted": the contractor can send a revised quote.
    session.commit()
    return view_quote(session, token)
