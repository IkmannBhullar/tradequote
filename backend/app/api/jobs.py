"""Job endpoints."""

import uuid

from fastapi import APIRouter, status

from app.api.deps import CurrentTenant, DbSession, PageParams
from app.models import Job
from app.models.enums import JobStatus
from app.schemas.common import Page
from app.schemas.jobs import JobCreate, JobOut, JobUpdate
from app.services import jobs as job_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _job_out(job: Job) -> JobOut:
    out = JobOut.model_validate(job)
    out.allowed_transitions = job_service.allowed_transitions(job.status)
    return out


@router.post("", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_job(body: JobCreate, tenant: CurrentTenant, session: DbSession) -> JobOut:
    job = job_service.create_job(
        session, tenant, client_id=body.client_id, title=body.title, address=body.address
    )
    return _job_out(job)


@router.get("", response_model=Page[JobOut])
def list_jobs(
    tenant: CurrentTenant,
    session: DbSession,
    page: PageParams,
    status: JobStatus | None = None,
    client_id: uuid.UUID | None = None,
) -> Page[JobOut]:
    """Newest first. Filter by `status` (e.g. for the job board) or `client_id`."""
    result = job_service.list_jobs(
        session, tenant, status=status, client_id=client_id, limit=page.limit, offset=page.offset
    )
    return Page(
        items=[_job_out(job) for job in result.items],
        total=result.total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: uuid.UUID, tenant: CurrentTenant, session: DbSession) -> JobOut:
    return _job_out(job_service.get_job(session, tenant, job_id))


@router.patch("/{job_id}", response_model=JobOut)
def update_job(
    job_id: uuid.UUID, body: JobUpdate, tenant: CurrentTenant, session: DbSession
) -> JobOut:
    changes = body.model_dump(exclude_unset=True)
    return _job_out(job_service.update_job(session, tenant, job_id, changes))
