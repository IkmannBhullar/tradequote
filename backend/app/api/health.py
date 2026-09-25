"""Health-check endpoints.

Two separate checks, a standard pattern for anything behind a load balancer
or orchestrator (e.g. AWS ECS/ALB, Kubernetes):

- **Liveness** (`/health`): "is the process up?" No dependencies. If this
  fails, the platform should restart the app.
- **Readiness** (`/health/ready`): "can it serve real traffic?" Checks the
  database. If this fails, the platform should stop sending traffic, but a
  restart won't help (the DB is the problem, not us).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db import get_db_session
from app.schemas.health import LivenessResponse, ReadinessResponse
from app.services import health as health_service

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=LivenessResponse)
def liveness() -> LivenessResponse:
    return LivenessResponse(status="ok")


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
def readiness(
    response: Response,
    session: Annotated[Session, Depends(get_db_session)],
) -> ReadinessResponse:
    # Router stays thin: ask the service, translate the answer into HTTP.
    if health_service.is_database_ready(session):
        return ReadinessResponse(status="ok", database="ok")

    # 503 tells load balancers "temporarily can't serve", distinct from a
    # 500 bug. We still return a JSON body explaining which dependency failed.
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(status="unavailable", database="unreachable")
