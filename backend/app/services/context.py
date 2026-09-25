"""The request's tenant context, passed from the HTTP layer into services."""

import uuid
from dataclasses import dataclass

from app.models.enums import UserRole


@dataclass(frozen=True)
class Tenant:
    """Who is calling, and which organization's data they may touch.

    Built ONLY from the authenticated user's database row (see
    api/deps.get_tenant). Services pass `organization_id` into tenant-scoped
    repositories; nothing in a request body or URL can change it
    (architecture rule 2).
    """

    organization_id: uuid.UUID
    user_id: uuid.UUID
    role: UserRole
