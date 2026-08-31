import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import RESOURCE_STATUSES, RESOURCE_TYPES


class ResourceCreateRequest(BaseModel):
    resource_type: str
    name: str = Field(min_length=1)
    notes: Optional[str] = None

    @field_validator("resource_type")
    @classmethod
    def resource_type_valid(cls, v):
        if v not in RESOURCE_TYPES:
            raise ValueError(f"resource_type must be one of {RESOURCE_TYPES}")
        return v


class ResourceUpdateRequest(BaseModel):
    status: Optional[str] = None
    name: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("status")
    @classmethod
    def status_valid(cls, v):
        if v is not None and v not in RESOURCE_STATUSES:
            raise ValueError(f"status must be one of {RESOURCE_STATUSES}")
        return v


class ResourceResponse(BaseModel):
    resource_id: uuid.UUID
    resource_type: str
    name: str
    status: str
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
