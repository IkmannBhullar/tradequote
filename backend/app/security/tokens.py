"""JWT access tokens.

A JWT is three base64 parts: header.payload.signature. The payload is NOT
encrypted (anyone can read it), so it holds only a user id. The signature is
an HMAC of header+payload using our secret: without the secret nobody can
produce a valid signature, so nobody can forge or edit a token.
"""

import uuid
from datetime import UTC, datetime, timedelta

import jwt

# Pinned algorithm. Verification accepts ONLY this, which blocks the classic
# attacks where a token claims "alg": "none" (no signature) or switches
# algorithms to trick the verifier.
ALGORITHM = "HS256"
# Who issued the token, and who it's for. Checking both means a token minted
# for some other system (even one sharing a secret by mistake) is rejected.
ISSUER = "tradequote-api"
AUDIENCE = "tradequote-app"
_REQUIRED_CLAIMS = ["exp", "iat", "sub", "iss", "aud"]


class InvalidTokenError(Exception):
    """The token is missing, malformed, expired, forged, or not ours."""


def create_access_token(
    user_id: uuid.UUID,
    *,
    secret: str,
    ttl: timedelta,
    now: datetime | None = None,  # injectable so tests can mint expired tokens
) -> str:
    issued_at = now or datetime.now(UTC)
    payload = {
        "sub": str(user_id),  # "subject": who this token is about
        "iat": issued_at,  # issued at
        "exp": issued_at + ttl,  # expires at
        "iss": ISSUER,
        "aud": AUDIENCE,
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_access_token(token: str, *, secret: str) -> uuid.UUID:
    """Verify the token and return the user id it was issued for.

    Checks the signature, expiry, issuer, audience, and that every required
    claim is present. Any failure raises InvalidTokenError: callers never need
    to know *why* a token was bad, and neither should an attacker.
    """
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[ALGORITHM],
            audience=AUDIENCE,
            issuer=ISSUER,
            options={"require": _REQUIRED_CLAIMS},
        )
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError) as error:
        # ValueError: the signature was valid but "sub" isn't a UUID.
        raise InvalidTokenError(str(error)) from error
