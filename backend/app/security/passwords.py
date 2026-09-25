"""Password hashing with Argon2id.

Why a special password hash, not SHA-256? General-purpose hashes are designed
to be FAST; an attacker with a leaked database can try billions of guesses per
second on a GPU. Argon2id is deliberately slow and memory-hungry (64 MB per
attempt here), which makes each guess expensive. It also salts every hash
automatically, so two users with the same password get different hashes.
"""

from functools import lru_cache

from pwdlib import PasswordHash

# pwdlib's recommended configuration: Argon2id with current best-practice cost
# parameters.
_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _hasher.verify(password, password_hash)


@lru_cache
def _dummy_hash() -> str:
    # Computed once, on first use, rather than at import time (hashing is slow).
    return _hasher.hash("dummy password used only to equalize timing")


def burn_verification_time(password: str) -> None:
    """Spend the same time a real verification would, then discard the result.

    Used when a login email doesn't exist. Without it, "unknown email" would
    answer instantly while "wrong password" takes ~50 ms, and an attacker
    could time responses to discover which emails have accounts.
    """
    _hasher.verify(password, _dummy_hash())
