import os
import uuid

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_claims, require_role
from app.payments.quotation_client import (
    QuotationAccessDenied,
    QuotationNotFound,
    QuotationServiceError,
    fetch_quotation,
)

app = FastAPI(
    title="payments-data",
    version="0.1.0",
    description="Payments and Split Settlement, Data and Analytics",
)

_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:5174,http://localhost:5175").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Trace-Id"],
)

# Schema is managed by Alembic (`alembic upgrade head`), not by the app.


def _error_body(code: str, message: str, request: Request) -> dict:
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
    return {"error": {"code": code, "message": message, "trace_id": trace_id}}


@app.middleware("http")
async def add_trace_id(request: Request, call_next):
    request.state.trace_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Trace-Id"] = request.state.trace_id
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        code, message = detail["code"], detail["message"]
    else:
        code, message = "ERROR", str(detail)
    return JSONResponse(status_code=exc.status_code, content=_error_body(code, message, request))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=_error_body("VALIDATION_ERROR", str(exc.errors()), request),
    )


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ready"}


# The quotation-fetch call is wrapped as an overridable dependency so tests
# don't need a live quotation service or httpx mocking - see tests/conftest.py.
def get_quotation_fetcher():
    return fetch_quotation


def _payment_to_response(p: models.Payment) -> schemas.PaymentResponse:
    return schemas.PaymentResponse(
        payment_id=p.id,
        job_id=p.job_id,
        quotation_id=p.quotation_id,
        amount=p.amount,
        status=p.status,
        created_at=p.created_at,
    )


@app.post("/v1/payments", response_model=schemas.PaymentResponse, status_code=201)
def create_payment(
    payload: schemas.PaymentCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_role("customer")),
    quotation_fetcher=Depends(get_quotation_fetcher),
):
    # FR-PAY-03: same idempotency_key never creates two payment records.
    # Checked BEFORE any cross-service call or insert - a replayed request
    # should short-circuit to the existing result, not repeat the work.
    existing = (
        db.query(models.Payment)
        .filter(models.Payment.idempotency_key == payload.idempotency_key)
        .first()
    )
    if existing:
        return _payment_to_response(existing)

    auth_header = request.headers.get("Authorization", "")
    try:
        quotation = quotation_fetcher(str(payload.quotation_id), auth_header)
    except QuotationNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "QUOTATION_NOT_FOUND", "message": "No quotation with this ID exists."},
        )
    except QuotationAccessDenied:
        # F-06: cascades correctly now that quotation service enforces real
        # ownership (F-01) - a customer paying against a quotation they
        # don't own gets a real 403 here, not a generic "service unavailable."
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "You do not have access to this quotation."},
        )
    except QuotationServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "QUOTATION_SERVICE_UNAVAILABLE",
                "message": f"Could not verify the quotation before charging: {exc}",
            },
        )

    # F-06: job_id and quotation_id are supplied separately by the client -
    # without this check, a valid, approved, correctly-priced quotation for
    # a DIFFERENT job could be paired with an unrelated job_id.
    if quotation.get("job_id") != str(payload.job_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "JOB_QUOTATION_MISMATCH",
                "message": "quotation_id does not belong to the given job_id.",
            },
        )

    # FR-PAY-01: customer must approve a quotation before payment.
    if quotation.get("status") != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "QUOTATION_NOT_APPROVED",
                "message": "This quotation has not been approved yet - approve it before paying.",
            },
        )

    # SRS section 6 validation rule: amount must exactly match the approved total.
    quoted_total = quotation.get("total_estimate")
    if quoted_total != payload.amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "AMOUNT_MISMATCH",
                "message": (
                    f"Payment amount ({payload.amount}) does not match the approved "
                    f"quotation total ({quoted_total})."
                ),
            },
        )

    payment = models.Payment(
        job_id=str(payload.job_id),
        quotation_id=str(payload.quotation_id),
        customer_id=claims["sub"],
        amount=payload.amount,
        idempotency_key=payload.idempotency_key,
        status="pending",
    )
    db.add(payment)
    try:
        db.commit()
    except IntegrityError:
        # Race: another request with the same idempotency_key committed
        # first between our SELECT and our INSERT. Return that one, not an
        # error - this is what "idempotent" actually means under concurrency.
        db.rollback()
        existing = (
            db.query(models.Payment)
            .filter(models.Payment.idempotency_key == payload.idempotency_key)
            .first()
        )
        return _payment_to_response(existing)
    db.refresh(payment)
    return _payment_to_response(payment)


@app.get("/v1/payments/{payment_id}", response_model=schemas.PaymentResponse)
def get_payment(
    payment_id: uuid.UUID,
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_claims),
):
    payment = db.query(models.Payment).filter(models.Payment.id == str(payment_id)).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PAYMENT_NOT_FOUND", "message": "No payment with this ID exists."},
        )
    if claims["role"] == "customer" and payment.customer_id != claims["sub"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "You can only view your own payments."},
        )
    return _payment_to_response(payment)


@app.get("/v1/payments", response_model=list[schemas.PaymentResponse])
def list_payments(db: Session = Depends(get_db), claims: dict = Depends(get_current_claims)):
    query = db.query(models.Payment)
    if claims["role"] == "customer":
        query = query.filter(models.Payment.customer_id == claims["sub"])
    return [_payment_to_response(p) for p in query.order_by(models.Payment.created_at.desc()).all()]


@app.post("/v1/payments/{payment_id}/confirm", response_model=schemas.PaymentResponse)
def confirm_payment(
    payment_id: uuid.UUID,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_role("admin")),
):
    """Placeholder for the real payment gateway's webhook (RFC 0001 section 7
    open decision: Razorpay has a first-party WhatsApp/India integration).
    Gated behind admin role only because no real gateway is wired up yet -
    the eventual webhook will authenticate via gateway signature
    verification, not an app-issued JWT role check. Replace this, don't
    build on top of it, once a real gateway is integrated."""
    payment = db.query(models.Payment).filter(models.Payment.id == str(payment_id)).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PAYMENT_NOT_FOUND", "message": "No payment with this ID exists."},
        )
    payment.status = "completed"
    db.commit()
    db.refresh(payment)
    return _payment_to_response(payment)


@app.post("/v1/payments/{payment_id}/fail", response_model=schemas.PaymentResponse)
def fail_payment(
    payment_id: uuid.UUID,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_role("admin")),
):
    """Same placeholder caveat as confirm_payment above."""
    payment = db.query(models.Payment).filter(models.Payment.id == str(payment_id)).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PAYMENT_NOT_FOUND", "message": "No payment with this ID exists."},
        )
    payment.status = "failed"
    db.commit()
    db.refresh(payment)
    return _payment_to_response(payment)
