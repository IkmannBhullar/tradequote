"""Job data access, scoped to one organization."""

import uuid

from sqlalchemy.orm import selectinload

from app.models import Job
from app.models.enums import JobStatus
from app.repositories.base import PageResult, TenantRepository


class JobRepository(TenantRepository[Job]):
    model = Job

    def search(
        self,
        *,
        status: JobStatus | None,
        client_id: uuid.UUID | None,
        limit: int,
        offset: int,
    ) -> PageResult[Job]:
        # Filters are added on top of _scoped(), never instead of it.
        # selectinload: one extra query loads every listed job's client,
        # instead of one query per job card (the N+1 problem).
        statement = self._scoped().options(selectinload(Job.client))
        if status is not None:
            statement = statement.where(Job.status == status)
        if client_id is not None:
            statement = statement.where(Job.client_id == client_id)
        return self._page(statement.order_by(Job.created_at.desc()), limit, offset)
