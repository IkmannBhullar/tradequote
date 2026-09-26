"""Payment data access, scoped to one organization."""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select

from app.models import Payment
from app.repositories.base import TenantRepository


class PaymentRepository(TenantRepository[Payment]):
    model = Payment

    def for_job(self, job_id: uuid.UUID) -> Sequence[Payment]:
        return self._session.scalars(
            self._scoped()
            .where(Payment.job_id == job_id)
            .order_by(Payment.received_on, Payment.created_at, Payment.id)
        ).all()

    def paid_cents(self, job_id: uuid.UUID) -> int:
        """Total of the job's payments that still count (not voided)."""
        total = self._session.scalar(
            select(func.coalesce(func.sum(Payment.amount_cents), 0)).where(
                Payment.organization_id == self._organization_id,
                Payment.job_id == job_id,
                Payment.voided_at.is_(None),
            )
        )
        return int(total or 0)
