"""The current user's profile and organization."""

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.auth import CurrentUserOut, MeResponse, OrganizationOut
from app.services import auth as auth_service

router = APIRouter(tags=["me"])


@router.get("/me", response_model=MeResponse)
def me(user: CurrentUser, session: DbSession) -> MeResponse:
    organization = auth_service.get_organization(session, user)
    return MeResponse(
        # from_attributes: build the schema by reading the ORM object's fields.
        user=CurrentUserOut.model_validate(user, from_attributes=True),
        organization=OrganizationOut.model_validate(organization, from_attributes=True),
    )
