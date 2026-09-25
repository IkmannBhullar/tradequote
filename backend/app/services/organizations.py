"""Organization settings (the rates new quotes copy)."""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Organization
from app.models.enums import UserRole
from app.repositories.organizations import OrganizationRepository
from app.services.context import Tenant
from app.services.errors import PermissionDeniedError


def update_organization(
    session: Session,
    tenant: Tenant,
    *,
    name: str | None = None,
    logo_url: str | None = None,
    clear_logo: bool = False,
    default_labor_rate_cents: int | None = None,
    tax_rate: Decimal | None = None,
) -> Organization:
    # Settings affect every future quote's prices, so only the owner may
    # change them.
    if tenant.role is not UserRole.OWNER:
        raise PermissionDeniedError("Only the owner can change organization settings")

    organization = OrganizationRepository(session).get(tenant.organization_id)
    assert organization is not None  # the tenant came from an existing user row

    if name is not None:
        organization.name = name
    if logo_url is not None or clear_logo:
        organization.logo_url = logo_url
    if default_labor_rate_cents is not None:
        organization.default_labor_rate_cents = default_labor_rate_cents
    if tax_rate is not None:
        organization.tax_rate = tax_rate
    # Existing quotes are unaffected: they carry their own rate snapshots.
    session.commit()
    return organization
