import uuid

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import get_current_claims, require_role
from app.job_state_machine import InvalidTransitionError, validate_transition
from app.security import create_access_token, hash_password, verify_password

app = FastAPI(
    title="platform-spine",
    version="0.1.0",
    description="Identity/RBAC, Job Orchestration state machine, Notifications, Gateway routing",
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
