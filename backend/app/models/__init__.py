"""SQLAlchemy ORM models (typed `Mapped[]` style).

Every model is imported here so that importing `app.models` registers all
tables on `Base.metadata`. Alembic relies on this to see the full schema; a
model missing from this list would be invisible to autogenerate.
"""

from app.models.base import Base
from app.models.client import Client
from app.models.job import Job
from app.models.organization import Organization
from app.models.payment import Payment
from app.models.quote import Quote, QuoteArea, QuoteLineItem
from app.models.rate_limit import RateLimitCounter
from app.models.trade_template import TemplateItem, TradeTemplate
from app.models.user import User

__all__ = [
    "Base",
    "Client",
    "Job",
    "Organization",
    "Payment",
    "Quote",
    "QuoteArea",
    "QuoteLineItem",
    "RateLimitCounter",
    "TemplateItem",
    "TradeTemplate",
    "User",
]
