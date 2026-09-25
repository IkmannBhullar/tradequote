"""User: a person who logs in and belongs to exactly one organization.

Login fields (password hash or external auth id) are added in Milestone 3,
once the auth approach is chosen.
"""

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin, str_enum
from app.models.enums import UserRole


class User(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        # Emails are case-insensitive in practice ("Bob@x.com" == "bob@x.com").
        # We store them lowercased (the service layer normalizes) and the
        # database refuses anything else, so the plain UNIQUE below is enough.
        CheckConstraint("email = lower(email)", name="email_lowercase"),
    )

    # Unique across the whole system: one email = one account = one org.
    # 320 chars is the maximum length of a valid email address.
    email: Mapped[str] = mapped_column(String(320), unique=True)
    role: Mapped[UserRole] = mapped_column(str_enum(UserRole, "user_role"))
