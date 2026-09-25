"""Client data access, scoped to one organization."""

from app.models import Client
from app.repositories.base import TenantRepository


class ClientRepository(TenantRepository[Client]):
    model = Client
