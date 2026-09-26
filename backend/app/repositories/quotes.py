"""Quote data access, scoped to one organization.

Areas and line items belong to a quote and are reached only through a quote
loaded here (so always within the tenant); they have no repository of their
own. Services change them through the quote's collections.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy.orm import selectinload

from app.models import Quote
from app.models.enums import QuoteStatus
from app.repositories.base import TenantRepository


class QuoteRepository(TenantRepository[Quote]):
    model = Quote

    def get_with_details(self, quote_id: uuid.UUID) -> Quote | None:
        # selectinload: fetch areas and line items up front in two extra
        # queries, instead of one lazy query per access later (the "N+1"
        # problem).
        return self._session.scalar(
            self._scoped()
            .where(Quote.id == quote_id)
            .options(selectinload(Quote.areas), selectinload(Quote.line_items))
        )

    def list_for_job(self, job_id: uuid.UUID) -> Sequence[Quote]:
        return self._session.scalars(
            self._scoped().where(Quote.job_id == job_id).order_by(Quote.version)
        ).all()

    def latest_for_job(self, job_id: uuid.UUID) -> Quote | None:
        return self._session.scalar(
            self._scoped().where(Quote.job_id == job_id).order_by(Quote.version.desc()).limit(1)
        )

    def latest_approved_for_job(self, job_id: uuid.UUID) -> Quote | None:
        """The approved quote that sets what the client owes (the newest one,
        if a revision was approved later)."""
        return self._session.scalar(
            self._scoped()
            .where(Quote.job_id == job_id, Quote.status == QuoteStatus.APPROVED)
            .order_by(Quote.version.desc())
            .limit(1)
        )
