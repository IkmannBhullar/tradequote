"""Request/response shapes for sign-up, login, and the current user."""

import uuid
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, EmailStr, Field, SecretStr, StringConstraints

from app.models.enums import UserRole

# Emails are case-insensitive in practice and stored lowercase (see User).
NormalizedEmail = Annotated[EmailStr, AfterValidator(lambda email: email.strip().lower())]

# SecretStr hides the value in repr/logs ("**********"), so a stray
# print(request) or error report can't leak it.
# 12+ chars, no composition rules ("must include a symbol"), per NIST
# guidance: length matters, forced complexity just produces "Password1!".
# The 128 cap stops someone sending a 10 MB "password" to burn server CPU in
# the (deliberately slow) hash function.
NewPassword = Annotated[SecretStr, Field(min_length=12, max_length=128)]


class SignupRequest(BaseModel):
    organization_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
    ]
    email: NormalizedEmail
    password: NewPassword


class LoginRequest(BaseModel):
    email: NormalizedEmail
    # No minimum on login: a wrong password should get the normal "invalid
    # email or password", not a hint about the rules.
    password: Annotated[SecretStr, Field(max_length=128)]


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int  # seconds, so clients know when to log in again


class CurrentUserOut(BaseModel):
    id: uuid.UUID
    email: str
    role: UserRole


class OrganizationOut(BaseModel):
    id: uuid.UUID
    name: str
    logo_url: str | None
    default_labor_rate_cents: int
    # Decimal is serialized as a JSON *string* ("0.05000"), never a float,
    # so no precision is lost on the way to the client.
    tax_rate: Decimal


class MeResponse(BaseModel):
    user: CurrentUserOut
    organization: OrganizationOut
