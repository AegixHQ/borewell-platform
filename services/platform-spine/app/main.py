import os
import uuid
from contextlib import asynccontextmanager
from decimal import ROUND_HALF_UP, Decimal

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import events, models, payment_consumer, quotation_client, schemas
from app.database import get_db
from app.deps import get_current_claims, require_role
from app.job_state_machine import InvalidTransitionError, validate_transition
from app.security import create_access_token, hash_password, verify_password


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    # Real event consumer - see app/payment_consumer.py's module docstring
    # for the full design rationale. Starting this here (not at import
    # time) means importing app.main in tests never spins up a background
    # thread/Redis connection unintentionally - it only starts when the
    # app itself actually starts (including under TestClient's `with`
    # form, which does trigger this - confirmed by running the real test
    # suite, not assumed).
    payment_consumer.start()
    yield


app = FastAPI(
    title="platform-spine",
    version="0.1.0",
    description="Identity/RBAC, Job Orchestration state machine, Notifications, Gateway routing",
    lifespan=_lifespan,
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
# The app deliberately does NOT call Base.metadata.create_all() - relying on
# implicit table creation is what breaks the first time migrations and model
# code drift apart. See services/platform-spine/README.md.


# ---------- shared error format (RFC 0001 section 5 / SRS section 8) ----------


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


# ---------- health ----------


@app.get("/healthz")
def healthz():
    """Liveness check - does the process respond at all."""
    return {"status": "ok"}


@app.get("/readyz")
def readyz(db: Session = Depends(get_db)):
    """Readiness check - can we actually reach the database."""
    db.execute(text("SELECT 1"))
    return {"status": "ready"}


# ---------- auth (FR-AUTH-01 .. FR-AUTH-04) ----------


@app.post("/v1/auth/register", response_model=schemas.TokenResponse, status_code=201)
def register(payload: schemas.RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "EMAIL_TAKEN", "message": "An account with this email already exists."},
        )
    user = models.User(
        email=payload.email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "EMAIL_TAKEN", "message": "An account with this email already exists."},
        )
    db.refresh(user)
    token = create_access_token(str(user.id), user.role)
    return schemas.TokenResponse(access_token=token, role=user.role)


@app.post("/v1/auth/login", response_model=schemas.TokenResponse)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "Email or password is incorrect."},
        )
    token = create_access_token(str(user.id), user.role)
    return schemas.TokenResponse(access_token=token, role=user.role)


# ---------- jobs (FR-JOB-01 .. FR-JOB-05) ----------


def _job_to_response(job: models.Job) -> schemas.JobResponse:
    return schemas.JobResponse(
        job_id=job.id,
        customer_id=job.customer_id,
        status=job.status,
        job_type=job.job_type,
        location=schemas.Location(lat=job.location_lat, lng=job.location_lng),
        created_at=job.created_at,
    )


@app.post("/v1/jobs", response_model=schemas.JobResponse, status_code=201)
def create_job(
    payload: schemas.JobCreateRequest,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_role("customer")),
):
    job = models.Job(
        customer_id=claims["sub"],
        location_lat=payload.location.lat,
        location_lng=payload.location.lng,
        job_type=payload.job_type,
        status="lead",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    # Fire-and-forget (see app/events.py) - a dropped event means quotation
    # service won't auto-react to this job, not that the job wasn't created.
    # The job row (just committed) is the authoritative record either way.
    events.job_created(
        job_id=job.id,
        customer_id=job.customer_id,
        location={"lat": job.location_lat, "lng": job.location_lng},
        created_at=job.created_at,
    )
    return _job_to_response(job)


@app.get("/v1/jobs", response_model=list[schemas.JobResponse])
def list_jobs(db: Session = Depends(get_db), claims: dict = Depends(get_current_claims)):
    query = db.query(models.Job)
    if claims["role"] == "customer":
        query = query.filter(models.Job.customer_id == claims["sub"])
    # Contractor/admin see all jobs - single-contractor MVP assumption (PRD section 8).
    return [_job_to_response(j) for j in query.order_by(models.Job.created_at.desc()).all()]


@app.get("/v1/jobs/{job_id}", response_model=schemas.JobResponse)
def get_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_claims),
):
    job = db.query(models.Job).filter(models.Job.id == str(job_id)).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "JOB_NOT_FOUND", "message": "No job with this ID exists."},
        )
    if claims["role"] == "customer" and job.customer_id != claims["sub"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "You can only view your own jobs."},
        )
    return _job_to_response(job)


@app.patch("/v1/jobs/{job_id}/status", response_model=schemas.JobResponse)
def advance_job_status(
    job_id: uuid.UUID,
    payload: schemas.JobStatusUpdateRequest,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_role("contractor", "admin")),
):
    job = db.query(models.Job).filter(models.Job.id == str(job_id)).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "JOB_NOT_FOUND", "message": "No job with this ID exists."},
        )
    try:
        validate_transition(job.status, payload.status)
    except InvalidTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_TRANSITION", "message": str(exc)},
        )
    job.status = payload.status
    db.commit()
    db.refresh(job)
    return _job_to_response(job)


# ---------- job completion (FR-TRACK-03, FR-TRACK-04) ----------


def _completion_to_response(c: models.JobCompletion) -> schemas.JobCompletionResponse:
    return schemas.JobCompletionResponse(
        job_id=c.job_id,
        actual_depth_ft=c.actual_depth_ft,
        depth_overage_ft=c.depth_overage_ft,
        actual_cost=c.actual_cost,
        quoted_total=c.quoted_total,
        variance=c.variance,
        depth_overage_charge=c.depth_overage_charge,
        completed_at=c.completed_at,
    )


@app.post(
    "/v1/jobs/{job_id}/completion",
    response_model=schemas.JobCompletionResponse,
    status_code=201,
)
def log_job_completion(
    job_id: uuid.UUID,
    payload: schemas.JobCompletionRequest,
    request: Request,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_role("contractor", "admin")),
):
    """Log actual depth and cost at completion. Only valid when status is
    'completion'. Only writable once (SRS section 5, BR-04). Fetches the
    approved quotation to compute variance and depth overage (BR-04/05)."""
    job = db.query(models.Job).filter(models.Job.id == str(job_id)).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "JOB_NOT_FOUND", "message": "No job with this ID exists."},
        )

    # FR-TRACK-03 acceptance criterion: reject if job isn't at completion.
    if job.status != "completion":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "JOB_NOT_AT_COMPLETION",
                "message": (
                    f"Job status is '{job.status}'. Completion can only be "
                    "logged when the job has reached the 'completion' stage."
                ),
            },
        )

    # BR-04: only writable once.
    existing = db.query(models.JobCompletion).filter(
        models.JobCompletion.job_id == str(job_id)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "ALREADY_COMPLETED",
                "message": ("A completion record already exists for this job "
                    "and cannot be overwritten (BR-04)."),
            },
        )

    # Fetch approved quotation to get quoted_total + depth range for
    # variance (BR-04) and depth overage (BR-05). The auth header is
    # forwarded so the quotation service can verify job ownership.
    auth_header = request.headers.get("Authorization", "")
    try:
        quotation = quotation_client.fetch_approved_quotation(str(job_id), auth_header)
    except quotation_client.QuotationNotFound:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "NO_APPROVED_QUOTATION",
                "message": ("No approved quotation found. A quotation must be "
                    "approved before logging completion."),
            },
        )
    except quotation_client.QuotationNotApproved as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "QUOTATION_NOT_APPROVED", "message": str(exc)},
        )
    except quotation_client.QuotationServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "QUOTATION_SERVICE_ERROR", "message": str(exc)},
        )

    quoted_total = quotation["total_estimate"]
    actual_cost = Decimal(str(payload.actual_cost))

    # BR-04: variance = actual_cost - quoted_total (negative = under budget).
    variance = actual_cost - quoted_total

    # BR-05: depth overage is priced at the contractor's configured
    # per-foot overage rate, applied transparently (SRS section 4) - the
    # rate snapshotted on the quotation at generation/edit time (quotation
    # service's models.Quotation docstring explains why it's a snapshot,
    # not a live lookup). Missing only for quotations that predate that
    # snapshot field (quotation service migration 0003) - for those, the
    # overage feet are still recorded and shown (never hidden), but the
    # charge honestly cannot be computed rather than silently defaulting
    # to 0 and looking like "no overage occurred" when one did.
    depth_overage_ft = max(0.0, payload.actual_depth_ft - quotation["max_ft"])
    overage_rate = quotation.get("depth_overage_rate_per_ft")
    if depth_overage_ft > 0 and overage_rate is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "OVERAGE_RATE_UNAVAILABLE",
                "message": (
                    f"Actual depth ({payload.actual_depth_ft} ft) exceeds the quoted "
                    f"max ({quotation['max_ft']} ft), but this quotation predates "
                    "per-foot overage rate tracking and has no rate to charge "
                    "against. Completion cannot be logged accurately - contact "
                    "an admin to resolve this specific quotation."
                ),
            },
        )
    depth_overage_charge = (
        (Decimal(str(depth_overage_ft)) * overage_rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        if depth_overage_ft > 0
        else Decimal("0")
    )

    from datetime import datetime, timezone
    completed_at = datetime.now(timezone.utc)

    completion = models.JobCompletion(
        job_id=str(job_id),
        actual_depth_ft=payload.actual_depth_ft,
        depth_overage_ft=depth_overage_ft,
        actual_cost=actual_cost,
        quoted_total=quoted_total,
        variance=variance,
        depth_overage_charge=depth_overage_charge,
        completed_at=completed_at,
    )
    db.add(completion)
    db.commit()
    db.refresh(completion)

    # job.completed event - now we have the real data the schema requires.
    events.job_completed(
        job_id=str(job_id),
        actual_depth_ft=payload.actual_depth_ft,
        actual_cost=actual_cost,
        completed_at=completed_at,
    )

    return _completion_to_response(completion)


@app.get(
    "/v1/jobs/{job_id}/completion/result",
    response_model=schemas.JobCompletionResponse,
)
def get_job_completion(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    claims: dict = Depends(get_current_claims),
):
    """Read completion record and variance (FR-TRACK-04). Customers can
    read their own job's record; contractor/admin can read any."""
    job = db.query(models.Job).filter(models.Job.id == str(job_id)).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "JOB_NOT_FOUND", "message": "No job with this ID exists."},
        )
    if claims["role"] == "customer" and job.customer_id != claims["sub"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN",
                "message": "You can only view your own job's completion record.",
            },
        )
    completion = db.query(models.JobCompletion).filter(
        models.JobCompletion.job_id == str(job_id)
    ).first()
    if not completion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "COMPLETION_NOT_FOUND",
                "message": "No completion record for this job yet.",
            },
        )
    return _completion_to_response(completion)
