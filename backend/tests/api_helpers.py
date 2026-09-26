"""Helpers for API integration tests: signed-up users and common calls."""

from dataclasses import dataclass
from typing import Any

from fastapi.testclient import TestClient

PASSWORD = "correct horse battery staple"


@dataclass
class ApiUser:
    """A signed-up owner, plus a thin wrapper that sends their token."""

    client: TestClient
    token: str
    organization_id: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def get(self, url: str, **kwargs: Any) -> Any:
        return self.client.get(url, headers=self.headers, **kwargs)

    def post(self, url: str, **kwargs: Any) -> Any:
        return self.client.post(url, headers=self.headers, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> Any:
        return self.client.patch(url, headers=self.headers, **kwargs)

    def put(self, url: str, **kwargs: Any) -> Any:
        return self.client.put(url, headers=self.headers, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> Any:
        return self.client.delete(url, headers=self.headers, **kwargs)

    # --- shortcuts that assert success and return the JSON body ---

    def ok(self, method: str, url: str, expected_status: int = 200, **kwargs: Any) -> Any:
        response = getattr(self, method)(url, **kwargs)
        assert response.status_code == expected_status, response.text
        return response.json() if response.content else None

    def create_client(self, name: str = "Jane Homeowner") -> dict[str, Any]:
        result: dict[str, Any] = self.ok("post", "/clients", 201, json={"name": name})
        return result

    def create_job(self, client_id: str | None = None) -> dict[str, Any]:
        client_id = client_id or self.create_client()["id"]
        result: dict[str, Any] = self.ok(
            "post", "/jobs", 201, json={"client_id": client_id, "title": "Repaint living room"}
        )
        return result

    def create_quote(self, job_id: str | None = None) -> dict[str, Any]:
        job_id = job_id or self.create_job()["id"]
        result: dict[str, Any] = self.ok("post", f"/jobs/{job_id}/quotes", 201)
        return result

    def template_item_id(self, name: str = "Walls") -> str:
        """Id of a system template item by name, whatever trade it's in."""
        templates = self.ok("get", "/templates")
        return str(
            next(
                item["id"]
                for template in templates
                if template["organization_id"] is None
                for item in template["items"]
                if item["name"] == name
            )
        )

    def add_area(self, quote_id: str, quantity: str = "420", **fields: Any) -> dict[str, Any]:
        body = {"template_item_id": self.template_item_id(), "name": "Living room walls"}
        body |= {"quantity": quantity, **fields}
        result: dict[str, Any] = self.ok("post", f"/quotes/{quote_id}/areas", 201, json=body)
        return result


def sign_up(client: TestClient, email: str, organization_name: str) -> ApiUser:
    response = client.post(
        "/auth/signup",
        json={"organization_name": organization_name, "email": email, "password": PASSWORD},
    )
    assert response.status_code == 201, response.text
    user = ApiUser(client=client, token=response.json()["access_token"], organization_id="")
    user.organization_id = user.ok("get", "/me")["organization"]["id"]
    return user
