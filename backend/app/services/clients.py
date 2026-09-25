"""Clients: the contractor's customers."""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import Client
from app.repositories.base import PageResult
from app.repositories.clients import ClientRepository
from app.services.context import Tenant
from app.services.errors import ConflictError, NotFoundError


def _repo(session: Session, tenant: Tenant) -> ClientRepository:
    return ClientRepository(session, tenant.organization_id)


def get_client(session: Session, tenant: Tenant, client_id: uuid.UUID) -> Client:
    client = _repo(session, tenant).get(client_id)
    if client is None:
        raise NotFoundError("Client")
    return client


def list_clients(
    session: Session, tenant: Tenant, *, limit: int, offset: int
) -> PageResult[Client]:
    return _repo(session, tenant).page(limit=limit, offset=offset)


def create_client(
    session: Session,
    tenant: Tenant,
    *,
    name: str,
    email: str | None,
    phone: str | None,
    address: str | None,
) -> Client:
    client = _repo(session, tenant).add(
        Client(name=name, email=email, phone=phone, address=address)
    )
    session.commit()
    return client


def update_client(
    session: Session, tenant: Tenant, client_id: uuid.UUID, changes: dict[str, Any]
) -> Client:
    """Apply only the fields the caller sent (PATCH semantics).

    `changes` comes from a validated schema, so its keys are known fields.
    """
    client = get_client(session, tenant, client_id)
    for field, value in changes.items():
        setattr(client, field, value)
    session.commit()
    return client


def delete_client(session: Session, tenant: Tenant, client_id: uuid.UUID) -> None:
    repo = _repo(session, tenant)
    client = get_client(session, tenant, client_id)
    # Checked here for a clear message; the RESTRICT foreign key would also
    # refuse, but as a generic database error.
    if repo.has_jobs(client_id):
        raise ConflictError("Client has jobs and can't be deleted")
    repo.delete(client)
    session.commit()
