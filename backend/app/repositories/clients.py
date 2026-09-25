"""Client data access, scoped to one organization."""

import uuid

from sqlalchemy import exists, select

from app.models import Client, Job
from app.repositories.base import TenantRepository


class ClientRepository(TenantRepository[Client]):
    model = Client

    def has_jobs(self, client_id: uuid.UUID) -> bool:
        return bool(
            self._session.scalar(
                select(
                    exists().where(
                        Job.organization_id == self._organization_id, Job.client_id == client_id
                    )
                )
            )
        )
