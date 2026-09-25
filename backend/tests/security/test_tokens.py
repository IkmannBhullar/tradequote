"""Access tokens: the happy path, then every way a token must be rejected."""

import base64
import json
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.security.tokens import (
    ALGORITHM,
    AUDIENCE,
    ISSUER,
    InvalidTokenError,
    create_access_token,
    decode_access_token,
)

# 64+ bytes: long enough even for the HS512 attack token below (RFC 7518 wants
# an HMAC key at least as long as the hash output: 32 bytes for HS256).
SECRET = "unit-test-secret-" + "x" * 64
HOUR = timedelta(hours=1)


def _claims(**changes: object) -> dict[str, object]:
    now = datetime.now(UTC)
    claims: dict[str, object] = {
        "sub": str(uuid.uuid4()),
        "iat": now,
        "exp": now + HOUR,
        "iss": ISSUER,
        "aud": AUDIENCE,
    }
    claims.update(changes)
    return {key: value for key, value in claims.items() if value is not None}


def test_round_trip_returns_the_user_id() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(user_id, secret=SECRET, ttl=HOUR)
    assert decode_access_token(token, secret=SECRET) == user_id


def test_payload_is_readable_but_holds_only_the_user_id() -> None:
    # JWTs are signed, NOT encrypted: anyone can base64-decode the payload.
    # That's why it must never contain secrets or personal data.
    user_id = uuid.uuid4()
    token = create_access_token(user_id, secret=SECRET, ttl=HOUR)
    payload_part = token.split(".")[1]
    payload = json.loads(base64.urlsafe_b64decode(payload_part + "=="))
    assert set(payload) == {"sub", "iat", "exp", "iss", "aud"}
    assert payload["sub"] == str(user_id)


def test_expired_token_is_rejected() -> None:
    two_hours_ago = datetime.now(UTC) - timedelta(hours=2)
    token = create_access_token(uuid.uuid4(), secret=SECRET, ttl=HOUR, now=two_hours_ago)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, secret=SECRET)


def test_token_signed_with_another_secret_is_rejected() -> None:
    token = create_access_token(uuid.uuid4(), secret="some-other-secret-0123456789abcdef", ttl=HOUR)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, secret=SECRET)


def test_tampered_payload_is_rejected() -> None:
    # Swap in someone else's user id but keep the original signature.
    token = create_access_token(uuid.uuid4(), secret=SECRET, ttl=HOUR)
    header, _, signature = token.split(".")
    forged_payload = jwt.encode(_claims(), SECRET, algorithm=ALGORITHM).split(".")[1]
    with pytest.raises(InvalidTokenError):
        decode_access_token(f"{header}.{forged_payload}.{signature}", secret=SECRET)


def test_alg_none_token_is_rejected() -> None:
    # The classic attack: an unsigned token claiming it needs no signature.
    unsigned = jwt.encode(_claims(), key=None, algorithm="none")
    with pytest.raises(InvalidTokenError):
        decode_access_token(unsigned, secret=SECRET)


def test_other_algorithm_is_rejected_even_with_our_secret() -> None:
    token = jwt.encode(_claims(), SECRET, algorithm="HS512")
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, secret=SECRET)


@pytest.mark.parametrize(
    "changes",
    [
        {"iss": "someone-else"},
        {"aud": "some-other-app"},
        {"exp": None},  # a token that never expires
        {"sub": None},
        {"sub": "not-a-uuid"},
    ],
    ids=["wrong-issuer", "wrong-audience", "no-expiry", "no-subject", "bad-subject"],
)
def test_bad_claims_are_rejected(changes: dict[str, object]) -> None:
    token = jwt.encode(_claims(**changes), SECRET, algorithm=ALGORITHM)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, secret=SECRET)


@pytest.mark.parametrize("garbage", ["", "not.a.jwt", "a.b", "🙂"])
def test_malformed_tokens_are_rejected(garbage: str) -> None:
    with pytest.raises(InvalidTokenError):
        decode_access_token(garbage, secret=SECRET)
