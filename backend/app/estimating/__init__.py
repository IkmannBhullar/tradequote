"""Pure estimating engine.

Plain inputs in, plain results out: no database, no HTTP, no I/O. Money is
integer cents and all math uses Decimal, never float.

Callers import from here (`from app.estimating import calculate_estimate`),
not from the submodules, so internals can be reorganized freely.
"""

from app.estimating.engine import calculate_estimate, estimate_area
from app.estimating.types import (
    AreaInput,
    Estimate,
    EstimatedLine,
    EstimateInput,
    ItemRates,
    LineKind,
    LineOverride,
)

__all__ = [
    "AreaInput",
    "Estimate",
    "EstimateInput",
    "EstimatedLine",
    "ItemRates",
    "LineKind",
    "LineOverride",
    "calculate_estimate",
    "estimate_area",
]
