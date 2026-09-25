"""Shared FastAPI dependencies: database session, settings, current user, tenant.

Protected endpoints declare what they need as parameters, e.g.

    def list_clients(tenant: CurrentTenant, session: DbSession): ...

and FastAPI runs the chain below before the endpoint body: read the Bearer
token -> verify it -> load the user -> derive the tenant. If any step fails,
the endpoint never runs and the client gets a 401.
"""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db_session
from app.models import User
from app.services import auth as auth_service
from app.services.context import Tenant

DbSession = Annotated[Session, Depends(get_db_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]

# auto_error=False: we raise our own 401 (with a consistent body and the
# WWW-Authenticate header) instead of FastAPI's default. Registering it as a
# security scheme also gives Swagger UI its "Authorize" button.
_bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        # Standard header telling the client which auth scheme to use.
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    session: DbSession,
    settings: AppSettings,
) -> User:
    if credentials is None:
        raise _unauthorized()
    try:
        return auth_service.resolve_current_user(session, settings, credentials.credentials)
    except auth_service.NotAuthenticatedError as error:
        # Same response whether the token was expired, forged, or for a
        # deleted user: no hints for an attacker.
        raise _unauthorized() from error


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_tenant(user: CurrentUser) -> Tenant:
    return Tenant(organization_id=user.organization_id, user_id=user.id, role=user.role)


CurrentTenant = Annotated[Tenant, Depends(get_tenant)]


@dataclass(frozen=True)
class Pagination:
    limit: int
    offset: int


def get_pagination(
    limit: Annotated[int, Query(ge=1, le=200, description="Max items to return")] = 50,
    offset: Annotated[int, Query(ge=0, description="Items to skip")] = 0,
) -> Pagination:
    # A hard upper limit stops one request from dumping a whole table.
    return Pagination(limit=limit, offset=offset)


PageParams = Annotated[Pagination, Depends(get_pagination)]
