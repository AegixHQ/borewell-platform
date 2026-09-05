import os
import uuid
from decimal import Decimal

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_claims, require_role
from app.estimation.engine import estimate_depth
from app.jobs.job_client import JobNotFound, JobServiceError, fetch_job
from app.pricing.engine import calculate_quotation, to_money

app = FastAPI(
    title="quotation",
    version="0.1.0",
    description="Location Intelligence and Estimation Engine, Quotation and Pricing Engine",
)

_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:5174,http://localhost:5175"
    ).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Trace-Id"],
)

# Schema is managed by Alembic (`alembic upgrade head`), not by the app -
# same discipline as platform-spine.


# ---------- shared error format (same pattern as platform-spine) ----------


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


# The job-fetch call is wrapped as an overridable dependency so tests don't
# need a live platform-spine or httpx mocking - same pattern as
# payments-data's get_quotation_fetcher. This is the fix for F-01: a
# quotation can no longer be created without proving the job exists and
# recording who its real customer is.
def get_job_fetcher():
    return fetch_job


# ---------- pricing rules (FR-K14) ----------


@app.post("/v1/pricing-rules", response_model=schemas.PricingRuleResponse)
def upsert_pricing_rule(
    payload: schemas.PricingRuleUpsertRequest,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_role("contractor")),
):
    existing = (
        db.query(models.PricingRule)
        .filter(
            models.PricingRule.contractor_id == claims["sub"],
            models.PricingRule.job_type == payload.job_type,
        )
        .first()
    )
    if existing:
        for field, value in payload.model_dump().items():
            setattr(existing, field, value)
        db.commit()
        db.refresh(existing)
        return existing

    rule = models.PricingRule(contractor_id=claims["sub"], **payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@app.get("/v1/pricing-rules", response_model=list[schemas.PricingRuleResponse])
def list_pricing_rules(
    db: Session = Depends(get_db), claims: dict = Depends(require_role("contractor"))
):
    return (
        db.query(models.PricingRule)
        .filter(models.PricingRule.contractor_id == claims["sub"])
        .all()
    )


# ---------- quotations (FR-QUOTE-01 .. FR-QUOTE-06) ----------


def _get_rule(db: Session, contractor_id: str, job_type: str):
    return (
        db.query(models.PricingRule)
        .filter(
            models.PricingRule.contractor_id == contractor_id,
            models.PricingRule.job_type == job_type,
        )
        .first()
    )


def _quotation_to_response(q: models.Quotation) -> schemas.QuotationResponse:
    return schemas.QuotationResponse(
        quotation_id=q.id,
        job_id=q.job_id,
        version=q.version,
        status=q.status,
        estimated_depth_range=schemas.DepthRange(
            min_ft=q.estimated_depth_min_ft,
            max_ft=q.estimated_depth_max_ft,
            confidence=q.confidence,
        ),
        line_items=[schemas.LineItem(**li) for li in q.line_items],
        subtotal=q.subtotal,
        margin_amount=q.margin_amount,
        minimum_charge_applied=q.minimum_charge_applied,
        total_estimate=q.total,
        created_at=q.created_at,
    )


def _require_quotation_access(quotation: models.Quotation, claims: dict) -> None:
    """The one authorization check every read/mutate endpoint below shares.
    Customers may only touch quotations for jobs they own; contractor/admin
    keep the existing single-contractor MVP assumption of seeing
    everything. This is F-01's actual fix - previously nothing here
    checked this at all."""
    if claims["role"] == "customer" and quotation.customer_id != claims["sub"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "You do not have access to this quotation."},
        )


@app.post("/v1/quotations", response_model=schemas.QuotationResponse, status_code=201)
def generate_quotation(
    payload: schemas.QuotationGenerateRequest,
    request: Request,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_role("contractor")),
    job_fetcher=Depends(get_job_fetcher),
):
    rule = _get_rule(db, claims["sub"], payload.job_type)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "PRICING_RULE_MISSING",
                "message": (
                    f"No pricing rule configured for job_type '{payload.job_type}'. "
                    "Configure one via POST /v1/pricing-rules before generating quotes."
                ),
            },
        )

    # F-01 fix: verify the job is real and capture its actual customer_id
    # from platform-spine, rather than trusting whatever the caller sent.
    auth_header = request.headers.get("Authorization", "")
    try:
        job = job_fetcher(str(payload.job_id), auth_header)
    except JobNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "JOB_NOT_FOUND", "message": "No job with this ID exists."},
        )
    except JobServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "JOB_SERVICE_UNAVAILABLE",
                "message": f"Could not verify the job before quoting: {exc}",
            },
        )

    # payload.location is part of the committed contract and will feed the
    # estimation engine once historical-data averaging ships (RFC 0001
    # section 6 / section 7, Sprint 7-8) - deliberately unused here in MVP.
    depth = estimate_depth(rule.assumed_depth_ft, rule.depth_confidence_band_ft)
    pricing = calculate_quotation(
        assumed_depth_ft=rule.assumed_depth_ft,
        base_rate_per_ft=rule.base_rate_per_ft,
        casing_rate_per_ft=rule.casing_rate_per_ft,
        labour_flat_fee=rule.labour_flat_fee,
        transport_flat_fee=rule.transport_flat_fee,
        equipment_flat_fee=rule.equipment_flat_fee,
        installation_flat_fee=rule.installation_flat_fee,
        margin_percent=rule.margin_percent,
        minimum_job_charge=rule.minimum_job_charge,
    )

    quotation = models.Quotation(
        job_id=str(payload.job_id),
        contractor_id=claims["sub"],
        customer_id=job["customer_id"],
        job_type=payload.job_type,
        version=1,
        status="draft",
        # Decimal isn't JSON-serializable - the JSON blob stores plain
        # floats (already rounded to 2dp by the pricing engine), while the
        # authoritative subtotal/margin_amount/total below stay Numeric.
        line_items=[{"label": li.label, "amount": float(li.amount)} for li in pricing.line_items],
        subtotal=pricing.subtotal,
        margin_amount=pricing.margin_amount,
        total=pricing.total,
        minimum_charge_applied=pricing.minimum_charge_applied,
        estimated_depth_min_ft=depth.min_ft,
        estimated_depth_max_ft=depth.max_ft,
        confidence=depth.confidence,
    )
    db.add(quotation)
    db.commit()
    db.refresh(quotation)
    return _quotation_to_response(quotation)


@app.get("/v1/quotations/{quotation_id}", response_model=schemas.QuotationResponse)
def get_quotation(
    quotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_claims),
):
    quotation = db.query(models.Quotation).filter(models.Quotation.id == str(quotation_id)).first()
    if not quotation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "QUOTATION_NOT_FOUND", "message": "No quotation with this ID exists."},
        )
    _require_quotation_access(quotation, claims)
    return _quotation_to_response(quotation)


@app.get("/v1/quotations/job/{job_id}/latest", response_model=schemas.QuotationResponse)
def get_latest_quotation_for_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_claims),
):
    quotation = (
        db.query(models.Quotation)
        .filter(models.Quotation.job_id == str(job_id))
        .order_by(models.Quotation.version.desc())
        .first()
    )
    if not quotation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "QUOTATION_NOT_FOUND",
                "message": "No quotation exists yet for this job.",
            },
        )
    _require_quotation_access(quotation, claims)
    return _quotation_to_response(quotation)


@app.patch(
    "/v1/quotations/{quotation_id}",
    response_model=schemas.QuotationResponse,
    status_code=201,
)
def edit_quotation(
    quotation_id: uuid.UUID,
    payload: schemas.QuotationEditRequest,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_role("contractor")),
):
    """201, not 200: an edit inserts a NEW quotation row (version + 1) rather
    than mutating the old one - see models.Quotation's docstring for why."""
    existing = db.query(models.Quotation).filter(models.Quotation.id == str(quotation_id)).first()
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "QUOTATION_NOT_FOUND", "message": "No quotation with this ID exists."},
        )
    if existing.contractor_id != claims["sub"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "You can only edit your own quotations."},
        )

    rule = _get_rule(db, existing.contractor_id, existing.job_type)
    minimum_job_charge = to_money(rule.minimum_job_charge) if rule else Decimal("0")

    if payload.line_items is not None:
        new_line_items = [{"label": li.label, "amount": li.amount} for li in payload.line_items]
        new_subtotal = to_money(
            sum((Decimal(str(li.amount)) for li in payload.line_items), Decimal("0"))
        )
    else:
        new_line_items = existing.line_items
        new_subtotal = to_money(existing.subtotal)

    if payload.total_estimate is not None:
        new_total = to_money(payload.total_estimate)
    elif payload.line_items is not None:
        # Manual line-item edit with no explicit total override: total
        # becomes the new subtotal - once a contractor hand-edits, they're
        # taking full control of the number, not asking the engine to
        # re-apply margin on top.
        new_total = new_subtotal
    else:
        new_total = to_money(existing.total)

    minimum_charge_applied = False
    if new_total < minimum_job_charge:
        new_total = minimum_job_charge
        minimum_charge_applied = True

    new_version = models.Quotation(
        job_id=existing.job_id,
        contractor_id=existing.contractor_id,
        customer_id=existing.customer_id,
        job_type=existing.job_type,
        version=existing.version + 1,
        status="draft",
        line_items=new_line_items,
        subtotal=new_subtotal,
        margin_amount=existing.margin_amount if payload.line_items is None else Decimal("0"),
        total=new_total,
        minimum_charge_applied=minimum_charge_applied,
        estimated_depth_min_ft=existing.estimated_depth_min_ft,
        estimated_depth_max_ft=existing.estimated_depth_max_ft,
        confidence=existing.confidence,
    )
    db.add(new_version)
    db.commit()
    db.refresh(new_version)
    return _quotation_to_response(new_version)


@app.post("/v1/quotations/{quotation_id}/approve", response_model=schemas.QuotationResponse)
def approve_quotation(
    quotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_role("customer")),
):
    quotation = db.query(models.Quotation).filter(models.Quotation.id == str(quotation_id)).first()
    if not quotation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "QUOTATION_NOT_FOUND", "message": "No quotation with this ID exists."},
        )
    _require_quotation_access(quotation, claims)
    quotation.status = "approved"
    db.commit()
    db.refresh(quotation)
    return _quotation_to_response(quotation)


@app.post("/v1/quotations/{quotation_id}/reject", response_model=schemas.QuotationResponse)
def reject_quotation(
    quotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_role("customer")),
):
    quotation = db.query(models.Quotation).filter(models.Quotation.id == str(quotation_id)).first()
    if not quotation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "QUOTATION_NOT_FOUND", "message": "No quotation with this ID exists."},
        )
    _require_quotation_access(quotation, claims)
    quotation.status = "rejected"
    db.commit()
    db.refresh(quotation)
    return _quotation_to_response(quotation)
