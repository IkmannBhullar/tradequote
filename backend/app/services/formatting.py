"""Formatting helpers shared by documents and messages (integer math only)."""


def format_cents(cents: int) -> str:
    """48300 -> "$483.00". divmod keeps it exact: no floats involved."""
    sign = "-" if cents < 0 else ""
    dollars, remainder = divmod(abs(cents), 100)
    return f"{sign}${dollars:,}.{remainder:02d}"
