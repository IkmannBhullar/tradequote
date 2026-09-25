"""Cross-tenant isolation: one organization can never read or modify another's data.

This is architecture rule 2, tested at two levels:
- repositories: the code path every future feature uses to touch tenant data;
- HTTP: the tenant is derived from the token's user, whatever the request says.
"""

import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentTenant
from app.models import Client, Organization
from app.repositories.clients import ClientRepository
from tests.factories import make_client, make_org
from tests.test_auth_api import bearer, token_for

# ---------------------------------------------------------------------------
# Repository level
# ---------------------------------------------------------------------------


def _two_tenants(session: Session) -> tuple[Organization, Organization, Client, Client]:
    org_a, org_b = make_org(session, "A"), make_org(session, "B")
    return (
        org_a,
        org_b,
        make_client(session, org_a, "A's client"),
        make_client(session, org_b, "B's client"),
    )


def test_get_cannot_reach_another_orgs_row(db_session: Session) -> None:
    org_a, _, client_a, client_b = _two_tenants(db_session)
    repo_a = ClientRepository(db_session, org_a.id)

    assert repo_a.get(client_a.id) == client_a
    # Looks exactly like "doesn't exist": no hint that the id is real.
    assert repo_a.get(client_b.id) is None


def test_list_returns_only_own_rows(db_session: Session) -> None:
    org_a, org_b, client_a, client_b = _two_tenants(db_session)

    assert ClientRepository(db_session, org_a.id).list() == [client_a]
    assert ClientRepository(db_session, org_b.id).list() == [client_b]


def test_add_always_uses_the_repositorys_org(db_session: Session) -> None:
    org_a, org_b, _, _ = _two_tenants(db_session)
    repo_a = ClientRepository(db_session, org_a.id)

    # A buggy (or malicious) caller tries to plant a row in org B.
    sneaky = repo_a.add(Client(organization_id=org_b.id, name="Planted"))

    assert sneaky.organization_id == org_a.id
    assert ClientRepository(db_session, org_b.id).get(sneaky.id) is None


def test_another_orgs_row_cannot_be_modified(db_session: Session) -> None:
    # To modify a row, code must first obtain it through its tenant's
    # repository, and org A's repository never returns org B's rows.
    org_a, _, _, client_b = _two_tenants(db_session)
    repo_a = ClientRepository(db_session, org_a.id)

    target = repo_a.get(client_b.id)

    assert target is None
    db_session.expire_all()
    unchanged = db_session.scalar(select(Client).where(Client.id == client_b.id))
    assert unchanged is not None and unchanged.name == "B's client"


# ---------------------------------------------------------------------------
# HTTP level
# ---------------------------------------------------------------------------


def test_each_user_sees_only_their_own_org(client: TestClient) -> None:
    token_a = token_for(client, email="a@a.example.com", organization_name="Org A")
    token_b = token_for(client, email="b@b.example.com", organization_name="Org B")

    assert client.get("/me", headers=bearer(token_a)).json()["organization"]["name"] == "Org A"
    assert client.get("/me", headers=bearer(token_b)).json()["organization"]["name"] == "Org B"


class _SpoofAttempt(BaseModel):
    organization_id: uuid.UUID


def test_tenant_ignores_org_ids_in_the_request(app: FastAPI, client: TestClient) -> None:
    # A throwaway endpoint (test-only) that echoes the resolved tenant, while
    # the caller tries to claim another org in the body.
    @app.post("/test-only/whoami")
    def whoami(body: _SpoofAttempt, tenant: CurrentTenant) -> dict[str, str]:
        return {"organization_id": str(tenant.organization_id)}

    token_a = token_for(client, email="a@a.example.com", organization_name="Org A")
    token_b = token_for(client, email="b@b.example.com", organization_name="Org B")
    org_a_id = client.get("/me", headers=bearer(token_a)).json()["organization"]["id"]
    org_b_id = client.get("/me", headers=bearer(token_b)).json()["organization"]["id"]

    response = client.post(
        "/test-only/whoami", json={"organization_id": org_b_id}, headers=bearer(token_a)
    )

    assert response.json() == {"organization_id": org_a_id}
