"""Enumerations shared by models, and later by schemas and services.

StrEnum members *are* strings (JobStatus.PAID == "paid"), so they serialize
to JSON naturally and compare cleanly with values read from the database.
"""

import enum


class UserRole(enum.StrEnum):
    OWNER = "owner"
    STAFF = "staff"


class MeasureType(enum.StrEnum):
    """How an area/template item is measured. Trade-agnostic on purpose."""

    AREA = "area"  # e.g. square feet of wall
    LINEAR = "linear"  # e.g. linear feet of baseboard
    COUNT = "count"  # e.g. number of doors


class JobStatus(enum.StrEnum):
    QUOTED = "quoted"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PAID = "paid"


class QuoteStatus(enum.StrEnum):
    DRAFT = "draft"
    SENT = "sent"
    APPROVED = "approved"
    DECLINED = "declined"


class PaymentKind(enum.StrEnum):
    DEPOSIT = "deposit"
    FINAL = "final"


class LineItemKind(enum.StrEnum):
    """Which calculated line a quote line item is. Mirrors the estimating
    engine's LineKind; the engine keeps its own copy so it never imports
    from the database layer."""

    MATERIAL = "material"
    LABOR = "labor"
