"""Public quote link tokens (architecture rule 8).

The raw token appears in exactly one place: the link given to the client.
The database stores only its SHA-256 hash, so a leaked database (or backup,
or log of SQL) can't be turned into working links.

Why a plain SHA-256 is enough here (unlike passwords, which need slow
Argon2): the token is 256 bits of randomness, not something a human chose,
so there's nothing to guess; hashing it quickly is fine.
"""

import hashlib
import secrets


def new_link_token() -> str:
    # 32 random bytes = 256 bits, URL-safe base64 (43 characters).
    return secrets.token_urlsafe(32)


def hash_link_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
