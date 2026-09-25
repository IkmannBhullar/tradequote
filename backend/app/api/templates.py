"""Trade templates (read-only for now)."""

from fastapi import APIRouter

from app.api.deps import CurrentTenant, DbSession
from app.schemas.templates import TemplateOut
from app.services import templates as template_service

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=list[TemplateOut])
def list_templates(tenant: CurrentTenant, session: DbSession) -> list[TemplateOut]:
    """System templates plus your organization's own, with their items."""
    return [
        TemplateOut.model_validate(template, from_attributes=True)
        for template in template_service.list_templates(session, tenant)
    ]
