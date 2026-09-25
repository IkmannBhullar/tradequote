"""Sign-up and login endpoints (public: no token required)."""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import AppSettings, DbSession
from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(issued: auth_service.IssuedToken) -> TokenResponse:
    return TokenResponse(access_token=issued.access_token, expires_in=issued.expires_in_seconds)


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, session: DbSession, settings: AppSettings) -> TokenResponse:
    """Create a new organization with you as its owner, and log you in."""
    try:
        issued = auth_service.sign_up(
            session,
            settings,
            organization_name=body.organization_name,
            email=body.email,
            # SecretStr keeps the password hidden until the moment it's needed.
            password=body.password.get_secret_value(),
        )
    except auth_service.EmailAlreadyRegisteredError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email is already registered"
        ) from error
    return _token_response(issued)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, session: DbSession, settings: AppSettings) -> TokenResponse:
    try:
        issued = auth_service.log_in(
            session, settings, email=body.email, password=body.password.get_secret_value()
        )
    except auth_service.InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    return _token_response(issued)
