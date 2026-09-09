import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PaymentCreateRequest(BaseModel):
    job_id: uuid.UUID
    quotation_id: uuid.UUID
    # Decimal, not float: compared for exact equality against the quotation's
    # total_estimate (SRS section 6). See fetch_quotation in
    # app/payments/quotation_client.py for how the comparison side is parsed.
    amount: Decimal = Field(gt=0)
    idempotency_key: str = Field(min_length=1)


class PaymentResponse(BaseModel):
    payment_id: uuid.UUID
    job_id: uuid.UUID
    quotation_id: uuid.UUID
    amount: Decimal
    status: str
    razorpay_order_id: str | None = None
    razorpay_payment_id: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CreateOrderResponse(BaseModel):
    razorpay_order_id: str
    razorpay_key_id: str
    amount_paise: int
    currency: str = "INR"
