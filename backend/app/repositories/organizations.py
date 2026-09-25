"""Organization data access.

Organizations ARE the tenants, so this repository isn't tenant-scoped itself:
callers pass the id they're allowed to see (always the current user's org).
"""

import uuid

from sqlalchemy.orm import Session

from app.models import Organization


class OrganizationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, name: str) -> Organization:
        organization = Organization(name=name)
        self._session.add(organization)
        self._session.flush()
        return organization

    def get(self, organization_id: uuid.UUID) -> Organization | None:
        return self._session.get(Organization, organization_id)
