"""Authentication: sign-up, login, and resolving the current user from a token.

Knows nothing about HTTP. It raises domain errors (below) and the router
decides which status code each one becomes.
"""

import uuid
from dataclasses import dataclass
from datetime import timedelta

import psycopg
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Organization, User
from app.models.enums import UserRole
from app.repositories.organizations import OrganizationRepository
from app.repositories.users import UserRepository
from app.security.passwords import burn_verification_time, hash_password, verify_password
from app.security.tokens import InvalidTokenError, create_access_token, decode_access_token

_UNIQUE_EMAIL_CONSTRAINT = "uq_users_email"


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    """Wrong email OR wrong password. Deliberately never says which."""


class NotAuthenticatedError(Exception):
    pass


@dataclass(frozen=True)
class IssuedToken:
    access_token: str
    expires_in_seconds: int


def normalize_email(email: str) -> str:
    # Also done by the request schema; repeated here so the service is
    # correct no matter who calls it.
    return email.strip().lower()


def _issue_token(user_id: uuid.UUID, settings: Settings) -> IssuedToken:
    ttl = timedelta(minutes=settings.access_token_ttl_minutes)
    token = create_access_token(user_id, secret=settings.jwt_secret, ttl=ttl)
    return IssuedToken(access_token=token, expires_in_seconds=int(ttl.total_seconds()))


def _is_duplicate_email(error: IntegrityError) -> bool:
    original = error.orig
    return (
        isinstance(original, psycopg.Error)
        and original.diag.constraint_name == _UNIQUE_EMAIL_CONSTRAINT
    )


def sign_up(
    session: Session, settings: Settings, *, organization_name: str, email: str, password: str
) -> IssuedToken:
    """Create a new organization and its owner in ONE transaction, then log in.

    Either both rows are created or neither is: we never leave an org with no
    owner, or a user with no org.
    """
    email = normalize_email(email)
    users = UserRepository(session)
    if users.get_by_email(email) is not None:
        raise EmailAlreadyRegisteredError(email)

    organization = OrganizationRepository(session).create(organization_name)
    try:
        user = users.create(
            organization_id=organization.id,
            email=email,
            role=UserRole.OWNER,
            password_hash=hash_password(password),
        )
    except IntegrityError as error:
        # Race condition: two sign-ups with the same email at the same moment
        # can both pass the check above. The UNIQUE constraint catches the
        # second one; we turn it into the same friendly error.
        session.rollback()
        if _is_duplicate_email(error):
            raise EmailAlreadyRegisteredError(email) from error
        raise

    session.commit()
    return _issue_token(user.id, settings)


def log_in(session: Session, settings: Settings, *, email: str, password: str) -> IssuedToken:
    user = UserRepository(session).get_by_email(normalize_email(email))
    if user is None:
        # Take as long as a real check so timing doesn't reveal that this
        # email has no account.
        burn_verification_time(password)
        raise InvalidCredentialsError
    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError
    return _issue_token(user.id, settings)


def resolve_current_user(session: Session, settings: Settings, token: str) -> User:
    """Token -> user id -> the user's row, freshly loaded from the database.

    Loading the row (instead of trusting claims inside the token) means a
    deleted user is locked out immediately, and their organization always
    comes from the database, never from anything the client sent.
    """
    try:
        user_id = decode_access_token(token, secret=settings.jwt_secret)
    except InvalidTokenError as error:
        raise NotAuthenticatedError from error

    user = UserRepository(session).get_by_id(user_id)
    if user is None:
        raise NotAuthenticatedError
    return user


def get_organization(session: Session, user: User) -> Organization:
    """The current user's organization (the one tenant they may see)."""
    organization = OrganizationRepository(session).get(user.organization_id)
    # Guaranteed by the NOT NULL foreign key; a None here is a real bug.
    assert organization is not None
    return organization
