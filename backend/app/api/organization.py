"""Organization settings."""

from fastapi import APIRouter

from app.api.deps import CurrentTenant, DbSession
from app.schemas.auth import OrganizationOut
from app.schemas.organization import OrganizationUpdate
from app.services import organizations as organization_service

router = APIRouter(prefix="/organization", tags=["organization"])


@router.patch("", response_model=OrganizationOut)
def update_organization(
    body: OrganizationUpdate, tenant: CurrentTenant, session: DbSession
) -> OrganizationOut:
    """Owner only. New quotes copy these rates; existing quotes keep theirs."""
    organization = organization_service.update_organization(
        session,
        tenant,
        name=body.name,
        logo_url=str(body.logo_url) if body.logo_url else None,
        clear_logo="logo_url" in body.model_fields_set and body.logo_url is None,
        default_labor_rate_cents=body.default_labor_rate_cents,
        tax_rate=body.tax_rate,
    )
    return OrganizationOut.model_validate(organization, from_attributes=True)
