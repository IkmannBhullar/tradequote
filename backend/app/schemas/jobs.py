"""Job request/response shapes."""

import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.enums import JobStatus
from app.schemas.common import LongText, Name, reject_explicit_nulls


class JobCreate(BaseModel):
    client_id: uuid.UUID
    title: Name
    address: LongText | None = None


class JobUpdate(BaseModel):
    title: Name | None = None
    address: LongText | None = None
    # Only manual board moves are allowed; see services/jobs.MANUAL_TRANSITIONS.
    status: JobStatus | None = None

    @model_validator(mode="after")
    def _required_not_null(self) -> Self:
        reject_explicit_nulls(self, ("title", "status"))
        return self


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    title: str
    address: str | None
    status: JobStatus
    created_at: datetime
