import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import JOB_TYPES


class PricingRuleUpsertRequest(BaseModel):
    job_type: str
    base_rate_per_ft: float = Field(gt=0)
    casing_rate_per_ft: float = Field(ge=0)
    labour_flat_fee: float = Field(ge=0)
    transport_flat_fee: float = Field(ge=0)
    equipment_flat_fee: float = Field(ge=0)
    installation_flat_fee: float = Field(ge=0)
    margin_percent: float = Field(ge=0, le=100)
    minimum_job_charge: float = Field(ge=0)
    assumed_depth_ft: float = Field(gt=0)
    depth_confidence_band_ft: float = Field(ge=0)
    depth_overage_rate_per_ft: float = Field(ge=0)

    @field_validator("job_type")
    @classmethod
    def job_type_valid(cls, v):
        if v not in JOB_TYPES:
            raise ValueError(f"job_type must be one of {JOB_TYPES}")
        return v


class PricingRuleResponse(PricingRuleUpsertRequest):
    id: uuid.UUID
    contractor_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)


class Location(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class QuotationGenerateRequest(BaseModel):
    job_id: uuid.UUID
    location: Location
    job_type: str

    @field_validator("job_type")
    @classmethod
    def job_type_valid(cls, v):
        if v not in JOB_TYPES:
            raise ValueError(f"job_type must be one of {JOB_TYPES}")
        return v


class LineItem(BaseModel):
    label: str
    amount: float


class DepthRange(BaseModel):
    min_ft: float
    max_ft: float
    confidence: str


class QuotationResponse(BaseModel):
    quotation_id: uuid.UUID
    job_id: uuid.UUID
    version: int
    status: str
    estimated_depth_range: DepthRange
    line_items: list[LineItem]
    subtotal: float
    margin_amount: float
    minimum_charge_applied: bool
    total_estimate: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QuotationEditRequest(BaseModel):
    line_items: Optional[list[LineItem]] = None
    total_estimate: Optional[float] = Field(default=None, gt=0)
