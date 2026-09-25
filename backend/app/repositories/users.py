"""User data access for authentication.

Deliberately NOT tenant-scoped: at login we don't know the tenant yet, because
the user record is what tells us. Only the auth service should use this; code
that works inside a tenant must go through TenantRepository subclasses.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.models.enums import UserRole


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self._session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        # Emails are stored lowercase (enforced by a CHECK constraint), and
        # the service normalizes input the same way before calling this.
        return self._session.scalar(select(User).where(User.email == email))

    def create(
        self, *, organization_id: uuid.UUID, email: str, role: UserRole, password_hash: str
    ) -> User:
        user = User(
            organization_id=organization_id, email=email, role=role, password_hash=password_hash
        )
        self._session.add(user)
        self._session.flush()
        return user
