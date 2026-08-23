import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models import JOB_STATUSES, ROLES


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    phone: Optional[str] = None
    role: str = Field(default="customer")

    @field_validator("role")
    @classmethod
    def role_must_be_valid(cls, v):
        if v not in ROLES:
            raise ValueError(f"role must be one of {ROLES}")
        return v

    @field_validator("phone")
    @classmethod
    def phone_format(cls, v):
        if v is None:
            return v
        digits = v.replace("+91", "").replace(" ", "").replace("-", "")
        if not (digits.isdigit() and len(digits) == 10):
            raise ValueError(
                "phone must be a valid 10-digit Indian mobile number, optionally prefixed with +91"
            )
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    role: str


class Location(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)

    @model_validator(mode="after")
    def reject_null_island(self):
        if self.lat == 0 and self.lng == 0:
            raise ValueError("lat/lng of (0, 0) is not a valid location")
        return self


class JobCreateRequest(BaseModel):
    location: Location
    job_type: str

    @field_validator("job_type")
    @classmethod
    def job_type_valid(cls, v):
        allowed = {"residential", "agricultural", "commercial"}
        if v not in allowed:
            raise ValueError(f"job_type must be one of {allowed}")
        return v


class JobResponse(BaseModel):
    job_id: uuid.UUID
    status: str
    job_type: str
    location: Location
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobStatusUpdateRequest(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def status_valid(cls, v):
        if v not in JOB_STATUSES:
            raise ValueError(f"status must be one of {JOB_STATUSES}")
        return v
