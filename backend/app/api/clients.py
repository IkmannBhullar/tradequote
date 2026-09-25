"""Client endpoints."""

import uuid

from fastapi import APIRouter, status

from app.api.deps import CurrentTenant, DbSession, PageParams
from app.schemas.clients import ClientCreate, ClientOut, ClientUpdate
from app.schemas.common import Page
from app.services import clients as client_service

router = APIRouter(prefix="/clients", tags=["clients"])


@router.post("", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
def create_client(body: ClientCreate, tenant: CurrentTenant, session: DbSession) -> ClientOut:
    client = client_service.create_client(session, tenant, **body.model_dump())
    return ClientOut.model_validate(client)


@router.get("", response_model=Page[ClientOut])
def list_clients(tenant: CurrentTenant, session: DbSession, page: PageParams) -> Page[ClientOut]:
    result = client_service.list_clients(session, tenant, limit=page.limit, offset=page.offset)
    return Page(
        items=[ClientOut.model_validate(client) for client in result.items],
        total=result.total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: uuid.UUID, tenant: CurrentTenant, session: DbSession) -> ClientOut:
    return ClientOut.model_validate(client_service.get_client(session, tenant, client_id))


@router.patch("/{client_id}", response_model=ClientOut)
def update_client(
    client_id: uuid.UUID, body: ClientUpdate, tenant: CurrentTenant, session: DbSession
) -> ClientOut:
    # exclude_unset: only fields the caller actually sent (PATCH semantics).
    changes = body.model_dump(exclude_unset=True)
    return ClientOut.model_validate(
        client_service.update_client(session, tenant, client_id, changes)
    )


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(client_id: uuid.UUID, tenant: CurrentTenant, session: DbSession) -> None:
    client_service.delete_client(session, tenant, client_id)
