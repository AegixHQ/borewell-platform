import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models import JOB_STATUSES, PUBLIC_ROLES


def _lowercase_email(v: str) -> str:
    # One account per address however it was typed: "Asha@X.com" and
    # "asha@x.com" used to be two different accounts. Lookups also compare
    # lower-cased, so accounts stored before this still match.
    return v.strip().lower()


def _password_fits_bcrypt(v: str) -> str:
    if len(v.encode("utf-8")) > 72:
        raise ValueError("password must be at most 72 bytes (about 72 characters)")
    return v


def _indian_mobile(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    digits = v.replace("+91", "").replace(" ", "").replace("-", "")
    if not (digits.isdigit() and len(digits) == 10):
        raise ValueError(
            "phone must be a valid 10-digit Indian mobile number, optionally prefixed with +91"
        )
    return v


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    phone: Optional[str] = Field(default=None, max_length=20)
    role: str = Field(default="customer")

    _email = field_validator("email")(_lowercase_email)
    _password = field_validator("password")(_password_fits_bcrypt)
    _phone = field_validator("phone")(_indian_mobile)

    @field_validator("role")
    @classmethod
    def role_must_be_valid(cls, v):
        if v not in PUBLIC_ROLES:
            raise ValueError(f"role must be one of {PUBLIC_ROLES}")
        return v


class AdminCreateContractorRequest(BaseModel):
    """An administrator adding a contractor. No role field on purpose: this
    endpoint can only ever create contractors, and extra fields are refused so
    a client cannot try to smuggle one in."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    phone: Optional[str] = Field(default=None, max_length=20)

    _email = field_validator("email")(_lowercase_email)
    _password = field_validator("password")(_password_fits_bcrypt)
    _phone = field_validator("phone")(_indian_mobile)


class UserSummary(BaseModel):
    user_id: uuid.UUID
    email: str
    phone: Optional[str] = None
    role: str
    created_at: Optional[datetime] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)

    _email = field_validator("email")(_lowercase_email)


class GoogleLoginRequest(BaseModel):
    id_token: str = Field(min_length=20, max_length=4096)
    # Only used when this Google account has no user here yet.
    role: Optional[str] = None

    @field_validator("role")
    @classmethod
    def role_must_be_valid(cls, v):
        if v is not None and v not in PUBLIC_ROLES:
            raise ValueError(f"role must be one of {PUBLIC_ROLES}")
        return v


class TokenResponse(BaseModel):
    access_token: str
    role: str
    # True only on the response that created the account (Google sign-in).
    new_account: bool = False


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


class WalkInJobCreateRequest(BaseModel):
    """A contractor opening a job for a customer who has no account."""

    customer_name: str = Field(min_length=1, max_length=100)
    customer_phone: str = Field(max_length=20)
    location: Location
    job_type: str

    @field_validator("customer_name")
    @classmethod
    def name_not_blank(cls, v):
        v = " ".join(v.split())
        if not v:
            raise ValueError("customer_name must not be blank")
        return v

    @field_validator("customer_phone")
    @classmethod
    def phone_format(cls, v):
        # Same rule as registration: a 10-digit Indian mobile, optional +91.
        digits = v.replace("+91", "").replace(" ", "").replace("-", "")
        if not (digits.isdigit() and len(digits) == 10):
            raise ValueError(
                "customer_phone must be a valid 10-digit Indian mobile number, "
                "optionally prefixed with +91"
            )
        return digits

    @field_validator("job_type")
    @classmethod
    def job_type_valid(cls, v):
        allowed = {"residential", "agricultural", "commercial"}
        if v not in allowed:
            raise ValueError(f"job_type must be one of {allowed}")
        return v


class JobResponse(BaseModel):
    job_id: uuid.UUID
    customer_id: uuid.UUID
    status: str
    job_type: str
    location: Location
    created_at: datetime
    # True for a job a contractor opened for a customer without an account.
    walk_in: bool = False
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class JobStatusUpdateRequest(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def status_valid(cls, v):
        if v not in JOB_STATUSES:
            raise ValueError(f"status must be one of {JOB_STATUSES}")
        return v


class JobCompletionRequest(BaseModel):
    actual_depth_ft: float = Field(gt=0)
    actual_cost: float = Field(gt=0)


class JobCompletionResponse(BaseModel):
    job_id: uuid.UUID
    actual_depth_ft: float
    depth_overage_ft: float
    # MONEY fields serialized as Decimal strings - same convention as
    # quotation and payments-data. See those services' schemas.py.
    actual_cost: Decimal
    quoted_total: Decimal
    variance: Decimal
    depth_overage_charge: Decimal
    completed_at: datetime

    model_config = ConfigDict(from_attributes=True)
