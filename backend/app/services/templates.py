"""Trade templates visible to an organization (read-only for now)."""

from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.models import TradeTemplate
from app.repositories.templates import TemplateRepository
from app.services.context import Tenant


def list_templates(session: Session, tenant: Tenant) -> Sequence[TradeTemplate]:
    return TemplateRepository(session, tenant.organization_id).list_visible()
