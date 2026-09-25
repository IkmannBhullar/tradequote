"""Integration tests for /clients."""

from typing import Any

import pytest

from tests.api_helpers import ApiUser


def test_create_and_get(owner: ApiUser) -> None:
    created = owner.ok(
        "post",
        "/clients",
        201,
        json={"name": "  Jane Homeowner ", "email": "jane@example.com", "phone": "555-0100"},
    )

    assert created["name"] == "Jane Homeowner"  # trimmed
    assert owner.ok("get", f"/clients/{created['id']}") == created


def test_list_is_paginated(owner: ApiUser) -> None:
    for name in ("A", "B", "C"):
        owner.create_client(name)

    first = owner.ok("get", "/clients", params={"limit": 2})
    rest = owner.ok("get", "/clients", params={"limit": 2, "offset": 2})

    assert (first["total"], first["limit"], first["offset"], len(first["items"])) == (3, 2, 0, 2)
    assert (rest["total"], len(rest["items"])) == (3, 1)
    # No row appears on two pages, none is skipped.
    names = {c["name"] for c in first["items"]} | {c["name"] for c in rest["items"]}
    assert names == {"A", "B", "C"}


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 201}, {"offset": -1}])
def test_bad_pagination_is_422(owner: ApiUser, params: dict[str, int]) -> None:
    assert owner.get("/clients", params=params).status_code == 422


def test_patch_changes_only_sent_fields_and_null_clears(owner: ApiUser) -> None:
    client = owner.ok(
        "post", "/clients", 201, json={"name": "Jane", "email": "jane@example.com", "phone": "1"}
    )

    updated = owner.ok("patch", f"/clients/{client['id']}", json={"email": None, "phone": "2"})

    assert (updated["name"], updated["email"], updated["phone"]) == ("Jane", None, "2")


@pytest.mark.parametrize(
    "body", [{"name": None}, {"name": ""}, {"email": "nope"}, {"phone": "x" * 51}]
)
def test_invalid_updates_are_422(owner: ApiUser, body: dict[str, Any]) -> None:
    client = owner.create_client()
    assert owner.patch(f"/clients/{client['id']}", json=body).status_code == 422


def test_delete(owner: ApiUser) -> None:
    client = owner.create_client()

    assert owner.delete(f"/clients/{client['id']}").status_code == 204
    assert owner.get(f"/clients/{client['id']}").status_code == 404


def test_client_with_jobs_cannot_be_deleted(owner: ApiUser) -> None:
    job = owner.create_job()

    response = owner.delete(f"/clients/{job['client_id']}")

    assert response.status_code == 409
    assert owner.get(f"/clients/{job['client_id']}").status_code == 200


def test_requires_authentication(client: Any) -> None:
    assert client.get("/clients").status_code == 401
