"""Rounding rules at their exact boundaries, where bugs hide."""

from decimal import Decimal

import pytest

from app.estimating.rounding import (
    round_half_up_to_cents,
    round_to_quarter_hour,
    round_up_to_whole_units,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0", 0),  # nothing needed, buy nothing
        ("0.0001", 1),  # any need at all means a whole unit
        ("2", 2),  # exact whole numbers are NOT bumped up
        ("2.000", 2),
        ("2.0001", 3),
        ("2.64", 3),
        ("2.99", 3),
    ],
)
def test_round_up_to_whole_units(value: str, expected: int) -> None:
    assert round_up_to_whole_units(Decimal(value)) == expected


@pytest.mark.parametrize(
    ("hours", "expected"),
    [
        ("0", "0.00"),
        ("0.12", "0.00"),  # documented edge case: tiny jobs round to 0 h (choice 2)
        ("0.124", "0.00"),
        ("0.125", "0.25"),  # exactly halfway between 0 and 0.25 -> up
        ("0.2", "0.25"),
        ("5.04", "5.00"),
        ("5.125", "5.25"),  # halfway -> up
        ("5.3749", "5.25"),
        ("5.375", "5.50"),
        ("5.875", "6.00"),
        ("7", "7.00"),
    ],
)
def test_round_to_quarter_hour(hours: str, expected: str) -> None:
    result = round_to_quarter_hour(Decimal(hours))
    assert result == Decimal(expected)
    # Always shown with two places, e.g. "5.00" not "5".
    assert str(result) == expected


@pytest.mark.parametrize(
    ("cents", "expected"),
    [
        ("0", 0),
        ("1625", 1625),
        ("1625.25", 1625),
        ("1625.49", 1625),
        ("1625.5", 1626),  # half-up...
        ("1626.5", 1627),  # ...even when the result is odd (banker's rounding would give 1626)
        ("1625.75", 1626),
    ],
)
def test_round_half_up_to_cents(cents: str, expected: int) -> None:
    assert round_half_up_to_cents(Decimal(cents)) == expected


def test_builtin_round_would_have_been_wrong() -> None:
    # Why the helpers exist: Python's round() uses banker's rounding.
    assert round(Decimal("1626.5")) == 1626
    assert round_half_up_to_cents(Decimal("1626.5")) == 1627
