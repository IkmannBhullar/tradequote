"""The estimating rounding rules, each defined in exactly one place.

Why not Python's built-in round()? It uses "banker's rounding" (round half to
even): round(2.5) == 2 and round(3.5) == 4. Customers and accountants expect
half-up (2.5 -> 3), so we pick the rounding mode explicitly every time.

All inputs are non-negative in practice (the engine validates its inputs).
"""

from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

_QUARTERS_PER_HOUR = 4
_HOURS_PLACES = Decimal("0.01")  # labor hours are always shown as e.g. 5.25


def round_up_to_whole_units(value: Decimal) -> int:
    """Materials: you can't buy 2.64 gallons, so always round UP (2.64 -> 3).

    An exact whole number stays as-is (3.000 -> 3), so we never add a
    spurious extra unit.
    """
    return int(value.to_integral_value(rounding=ROUND_CEILING))


def round_to_quarter_hour(hours: Decimal) -> Decimal:
    """Labor: round to the nearest 0.25 h, with exact halfway points going up.

    Trick: count in quarter-hours, round that to a whole number, convert back.
    5.04 h = 20.16 quarters -> 20 -> 5.00 h
    0.125 h = 0.5 quarters -> 1 -> 0.25 h  (halfway rounds up)
    """
    quarters = (hours * _QUARTERS_PER_HOUR).to_integral_value(rounding=ROUND_HALF_UP)
    return (quarters / _QUARTERS_PER_HOUR).quantize(_HOURS_PLACES)


def round_half_up_to_cents(amount_in_cents: Decimal) -> int:
    """Money: fractional cents round half-up to a whole cent (1625.5 -> 1626)."""
    return int(amount_in_cents.to_integral_value(rounding=ROUND_HALF_UP))
