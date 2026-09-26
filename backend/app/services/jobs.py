"""Jobs: work for a client, tracked from quote to paid."""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import Job
from app.models.enums import JobStatus
from app.repositories.base import PageResult
from app.repositories.jobs import JobRepository
from app.services import clients as client_service
from app.services import payments as payment_service
from app.services.context import Tenant
from app.services.errors import ConflictError, NotFoundError

# Status moves a user may make by hand (the job board). The others are made
# by the system: quoted -> approved when the client approves a quote, and
# completed <-> paid by the balance (see services/payments.settle_job_status).
# One step back is allowed everywhere to fix mistakes.
MANUAL_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.APPROVED: frozenset({JobStatus.SCHEDULED}),
    JobStatus.SCHEDULED: frozenset({JobStatus.APPROVED, JobStatus.IN_PROGRESS}),
    JobStatus.IN_PROGRESS: frozenset({JobStatus.SCHEDULED, JobStatus.COMPLETED}),
    JobStatus.COMPLETED: frozenset({JobStatus.IN_PROGRESS}),
}


def allowed_transitions(status: JobStatus) -> list[JobStatus]:
    """Manual moves available from `status`, in pipeline order (for the UI)."""
    allowed = MANUAL_TRANSITIONS.get(status, frozenset())
    return [candidate for candidate in JobStatus if candidate in allowed]


def _repo(session: Session, tenant: Tenant) -> JobRepository:
    return JobRepository(session, tenant.organization_id)


def get_job(session: Session, tenant: Tenant, job_id: uuid.UUID) -> Job:
    job = _repo(session, tenant).get(job_id)
    if job is None:
        raise NotFoundError("Job")
    return job


def list_jobs(
    session: Session,
    tenant: Tenant,
    *,
    status: JobStatus | None,
    client_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> PageResult[Job]:
    return _repo(session, tenant).search(
        status=status, client_id=client_id, limit=limit, offset=offset
    )


def create_job(
    session: Session, tenant: Tenant, *, client_id: uuid.UUID, title: str, address: str | None
) -> Job:
    # Looked up through the tenant: another org's client is "not found".
    # (The composite foreign key would also refuse it, as a backstop.)
    client_service.get_client(session, tenant, client_id)
    job = _repo(session, tenant).add(Job(client_id=client_id, title=title, address=address))
    session.commit()
    return job


def update_job(session: Session, tenant: Tenant, job_id: uuid.UUID, changes: dict[str, Any]) -> Job:
    job = get_job(session, tenant, job_id)
    new_status = changes.pop("status", None)
    if new_status is not None and new_status != job.status:
        if new_status not in MANUAL_TRANSITIONS.get(job.status, frozenset()):
            raise ConflictError(f"Can't move a job from {job.status} to {new_status}")
        job.status = new_status
        # Completing a job that's already fully paid makes it "paid" at once.
        payment_service.settle_job_status(session, tenant.organization_id, job)
    for field, value in changes.items():
        setattr(job, field, value)
    session.commit()
    return job
