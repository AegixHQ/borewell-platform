import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PaymentCreateRequest(BaseModel):
    job_id: uuid.UUID
    quotation_id: uuid.UUID
    amount: float = Field(gt=0)
    idempotency_key: str = Field(min_length=1)


class PaymentResponse(BaseModel):
    payment_id: uuid.UUID
    job_id: uuid.UUID
    quotation_id: uuid.UUID
    amount: float
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
