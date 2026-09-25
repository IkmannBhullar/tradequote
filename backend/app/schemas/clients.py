"""Client request/response shapes."""

import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, EmailStr, model_validator

from app.schemas.common import LongText, Name, ShortText, reject_explicit_nulls


class ClientCreate(BaseModel):
    name: Name
    email: EmailStr | None = None
    phone: ShortText | None = None
    address: LongText | None = None


class ClientUpdate(BaseModel):
    """PATCH: every field optional; send null to clear an optional field."""

    name: Name | None = None
    email: EmailStr | None = None
    phone: ShortText | None = None
    address: LongText | None = None

    @model_validator(mode="after")
    def _name_not_null(self) -> Self:
        reject_explicit_nulls(self, ("name",))
        return self


class ClientOut(BaseModel):
    # from_attributes: build directly from the ORM object's attributes.
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str | None
    phone: str | None
    address: str | None
    created_at: datetime
