"""Password hashing."""

from app.security.passwords import burn_verification_time, hash_password, verify_password

PASSWORD = "correct horse battery staple"


def test_hash_verifies_the_right_password_only() -> None:
    password_hash = hash_password(PASSWORD)
    assert verify_password(PASSWORD, password_hash) is True
    assert verify_password(PASSWORD + "!", password_hash) is False


def test_hash_is_argon2id_and_never_contains_the_password() -> None:
    password_hash = hash_password(PASSWORD)
    assert password_hash.startswith("$argon2id$")
    assert PASSWORD not in password_hash


def test_same_password_hashes_differently_each_time() -> None:
    # A random salt per hash: identical passwords can't be spotted in a leak,
    # and precomputed "rainbow tables" are useless.
    assert hash_password(PASSWORD) != hash_password(PASSWORD)


def test_burn_verification_time_accepts_any_password() -> None:
    # Only its timing matters; it must never raise.
    burn_verification_time("anything")
