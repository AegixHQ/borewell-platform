import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import RESOURCE_STATUSES, RESOURCE_TYPES


class ResourceCreateRequest(BaseModel):
    resource_type: str
    name: str = Field(min_length=1)
    notes: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    # Decimal, not float - same MONEY convention as every other price field
    # in the platform (Bug 2 fix). Optional: a resource can be registered
    # before its rate is known and priced later via PATCH.
    hourly_rate: Optional[Decimal] = Field(default=None, gt=0)
    vehicle_type: Optional[str] = None

    @field_validator("resource_type")
    @classmethod
    def resource_type_valid(cls, v):
        if v not in RESOURCE_TYPES:
            raise ValueError(f"resource_type must be one of {RESOURCE_TYPES}")
        return v

    @field_validator("lat")
    @classmethod
    def lat_valid(cls, v):
        if v is not None and not (-90 <= v <= 90):
            raise ValueError("lat must be between -90 and 90")
        return v

    @field_validator("lng")
    @classmethod
    def lng_valid(cls, v):
        if v is not None and not (-180 <= v <= 180):
            raise ValueError("lng must be between -180 and 180")
        return v


class ResourceUpdateRequest(BaseModel):
    status: Optional[str] = None
    name: Optional[str] = None
    notes: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    hourly_rate: Optional[Decimal] = Field(default=None, gt=0)
    vehicle_type: Optional[str] = None

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
    lat: Optional[float] = None
    lng: Optional[float] = None
    hourly_rate: Optional[Decimal] = None
    vehicle_type: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResourceMatchRequest(BaseModel):
    lat: float
    lng: float
    resource_type: Optional[str] = None
    max_results: int = Field(default=5, ge=1, le=20)

    @field_validator("lat")
    @classmethod
    def lat_valid(cls, v):
        if not (-90 <= v <= 90):
            raise ValueError("lat must be between -90 and 90")
        return v

    @field_validator("lng")
    @classmethod
    def lng_valid(cls, v):
        if not (-180 <= v <= 180):
            raise ValueError("lng must be between -180 and 180")
        return v

    @field_validator("resource_type")
    @classmethod
    def resource_type_valid(cls, v):
        if v is not None and v not in RESOURCE_TYPES:
            raise ValueError(f"resource_type must be one of {RESOURCE_TYPES}")
        return v


class ResourceMatchResult(BaseModel):
    resource_id: uuid.UUID
    name: str
    resource_type: str
    status: str
    hourly_rate: Optional[Decimal] = None
    vehicle_type: Optional[str] = None
    distance_km: float


class ServiceAreaUpsertRequest(BaseModel):
    name: str = Field(min_length=1)
    district: str = Field(min_length=1)
    state: str = Field(min_length=1)
    center_lat: float
    center_lng: float
    radius_km: float = Field(gt=0)
    estimated_water_depth_ft: float = Field(gt=0)
    confidence_band_ft: float = Field(ge=0)

    @field_validator("center_lat")
    @classmethod
    def lat_valid(cls, v):
        if not (-90 <= v <= 90):
            raise ValueError("center_lat must be between -90 and 90")
        return v

    @field_validator("center_lng")
    @classmethod
    def lng_valid(cls, v):
        if not (-180 <= v <= 180):
            raise ValueError("center_lng must be between -180 and 180")
        return v


class ServiceAreaResponse(BaseModel):
    area_id: uuid.UUID
    name: str
    district: str
    state: str
    center_lat: float
    center_lng: float
    radius_km: float
    estimated_water_depth_ft: float
    confidence_band_ft: float
    source: str
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BookingRequestCreate(BaseModel):
    resource_id: uuid.UUID
    job_id: Optional[uuid.UUID] = None
    message: Optional[str] = None


class BookingRequestResponse(BaseModel):
    booking_id: uuid.UUID
    resource_id: uuid.UUID
    owner_id: uuid.UUID
    contractor_id: uuid.UUID
    job_id: Optional[uuid.UUID] = None
    status: str
    message: Optional[str] = None
    created_at: datetime
    responded_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
