"""Integration tests for sign-up, login, and /me."""

import uuid
from datetime import UTC, datetime, timedelta

import httpx2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Organization, User
from app.models.enums import UserRole
from app.repositories.users import UserRepository
from app.security.tokens import create_access_token
from app.services import auth as auth_service

PASSWORD = "correct horse battery staple"


def signup(
    client: TestClient,
    email: str = "owner@acme.example.com",
    organization_name: str = "Acme Painting",
    password: str = PASSWORD,
) -> httpx2.Response:
    return client.post(
        "/auth/signup",
        json={"organization_name": organization_name, "email": email, "password": password},
    )


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def token_for(client: TestClient, **signup_kwargs: str) -> str:
    response = signup(client, **signup_kwargs)
    assert response.status_code == 201, response.text
    token: str = response.json()["access_token"]
    return token


# ---------------------------------------------------------------------------
# Sign-up
# ---------------------------------------------------------------------------


class TestSignup:
    def test_creates_org_and_owner_and_logs_in(self, client: TestClient) -> None:
        response = signup(
            client, email="  Owner@Acme.example.COM ", organization_name=" Acme Painting "
        )

        assert response.status_code == 201
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["expires_in"] == 60 * 60

        me = client.get("/me", headers=bearer(body["access_token"])).json()
        assert me["user"]["email"] == "owner@acme.example.com"  # trimmed + lowercased
        assert me["user"]["role"] == "owner"
        assert me["organization"]["name"] == "Acme Painting"  # trimmed
        assert me["organization"]["tax_rate"] == "0.00000"  # Decimal as a string, not a float

    def test_stores_an_argon2_hash_not_the_password(
        self, client: TestClient, db_session: Session
    ) -> None:
        signup(client)
        user = db_session.scalar(select(User).where(User.email == "owner@acme.example.com"))
        assert user is not None
        assert user.password_hash.startswith("$argon2id$")
        assert PASSWORD not in user.password_hash

    def test_duplicate_email_is_rejected_regardless_of_case(self, client: TestClient) -> None:
        assert signup(client, email="owner@acme.example.com").status_code == 201

        response = signup(client, email="OWNER@acme.example.com", organization_name="Other Co")

        assert response.status_code == 409
        assert response.json() == {"detail": "Email is already registered"}

    def test_failed_signup_creates_nothing(self, client: TestClient, db_session: Session) -> None:
        signup(client)
        organizations_before = db_session.scalars(select(Organization)).all()

        signup(client, organization_name="Should Not Exist")  # duplicate email

        assert db_session.scalars(select(Organization)).all() == organizations_before

    @pytest.mark.parametrize(
        ("changes", "field"),
        [
            ({"password": "11 chars..."}, "password"),
            ({"password": "x" * 129}, "password"),
            ({"email": "not-an-email"}, "email"),
            ({"organization_name": "   "}, "organization_name"),
        ],
    )
    def test_invalid_input_is_rejected(
        self, client: TestClient, changes: dict[str, str], field: str
    ) -> None:
        response = signup(client, **changes)

        assert response.status_code == 422
        assert [error["loc"][-1] for error in response.json()["detail"]] == [field]

    def test_validation_errors_never_echo_the_password(self, client: TestClient) -> None:
        secret = "Sh0rtSecret"  # 11 chars: too short, so validation fails
        response = signup(client, password=secret)

        assert response.status_code == 422
        assert secret not in response.text
        # Still useful to the client: which field, and the rule it broke.
        error = response.json()["detail"][0]
        assert error["loc"] == ["body", "password"]
        assert error["ctx"]["min_length"] == 12


def test_signup_race_on_the_same_email_becomes_a_conflict(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Simulate two simultaneous sign-ups: the "is this email taken?" check
    # says no, but the row already exists, so the UNIQUE constraint fires.
    settings = get_settings()
    auth_service.sign_up(
        db_session,
        settings,
        organization_name="First",
        email="dup@x.example.com",
        password=PASSWORD,
    )
    monkeypatch.setattr(UserRepository, "get_by_email", lambda self, email: None)

    with pytest.raises(auth_service.EmailAlreadyRegisteredError):
        auth_service.sign_up(
            db_session,
            settings,
            organization_name="Second",
            email="dup@x.example.com",
            password=PASSWORD,
        )


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


class TestLogin:
    def test_correct_credentials_return_a_working_token(self, client: TestClient) -> None:
        signup(client)

        response = client.post(
            "/auth/login", json={"email": "OWNER@acme.example.com", "password": PASSWORD}
        )

        assert response.status_code == 200
        me = client.get("/me", headers=bearer(response.json()["access_token"]))
        assert me.json()["user"]["email"] == "owner@acme.example.com"

    def test_wrong_password_and_unknown_email_look_identical(self, client: TestClient) -> None:
        signup(client)

        wrong_password = client.post(
            "/auth/login", json={"email": "owner@acme.example.com", "password": "wrong password!!"}
        )
        unknown_email = client.post(
            "/auth/login", json={"email": "nobody@acme.example.com", "password": PASSWORD}
        )

        # Same status, same body: an attacker can't tell which emails exist.
        assert wrong_password.status_code == unknown_email.status_code == 401
        assert (
            wrong_password.json() == unknown_email.json() == {"detail": "Invalid email or password"}
        )


# ---------------------------------------------------------------------------
# /me and token handling
# ---------------------------------------------------------------------------


class TestMe:
    def test_requires_a_token(self, client: TestClient) -> None:
        response = client.get("/me")
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"

    @pytest.mark.parametrize("header", ["Bearer not-a-jwt", "Basic dXNlcjpwYXNz", "Bearer "])
    def test_rejects_malformed_credentials(self, client: TestClient, header: str) -> None:
        assert client.get("/me", headers={"Authorization": header}).status_code == 401

    def test_rejects_an_expired_token(self, client: TestClient, db_session: Session) -> None:
        signup(client)
        user = db_session.scalar(select(User))
        assert user is not None
        expired = create_access_token(
            user.id,
            secret=get_settings().jwt_secret,
            ttl=timedelta(minutes=60),
            now=datetime.now(UTC) - timedelta(hours=2),
        )
        assert client.get("/me", headers=bearer(expired)).status_code == 401

    def test_rejects_a_token_signed_with_another_secret(self, client: TestClient) -> None:
        forged = create_access_token(
            uuid.uuid4(), secret="attacker-secret-" + "x" * 40, ttl=timedelta(minutes=60)
        )
        assert client.get("/me", headers=bearer(forged)).status_code == 401

    def test_deleted_user_is_locked_out_immediately(
        self, client: TestClient, db_session: Session
    ) -> None:
        token = token_for(client)
        assert client.get("/me", headers=bearer(token)).status_code == 200

        db_session.execute(delete(User))  # e.g. the owner removes a staff member

        # The token itself is still valid, but the user row is gone.
        assert client.get("/me", headers=bearer(token)).status_code == 401

    def test_role_comes_from_the_database(self, client: TestClient, db_session: Session) -> None:
        token = token_for(client)
        user = db_session.scalar(select(User))
        assert user is not None
        user.role = UserRole.STAFF  # e.g. demoted
        db_session.flush()

        # Same token, new role: nothing about permissions is baked into it.
        assert client.get("/me", headers=bearer(token)).json()["user"]["role"] == "staff"
