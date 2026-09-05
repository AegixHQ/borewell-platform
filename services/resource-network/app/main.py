import os
import uuid

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import require_role

app = FastAPI(
    title="resource-network",
    version="0.1.0",
    description="Resource Matching Engine, Inventory (rig/equipment/labour), Document/Media",
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
# Inventory CRUD only in MVP - matching engine is Phase 1 (see app/matching/).
# Resources are owned and managed by the contractor in MVP; there is no
# independent resource_owner self-service access to this service yet -
# see AGENTS.md and the Phase 1 boundary noted there.


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


def _resource_to_response(r: models.Resource) -> schemas.ResourceResponse:
    return schemas.ResourceResponse(
        resource_id=r.id,
        resource_type=r.resource_type,
        name=r.name,
        status=r.status,
        notes=r.notes,
        created_at=r.created_at,
    )


@app.post("/v1/resources", response_model=schemas.ResourceResponse, status_code=201)
def create_resource(
    payload: schemas.ResourceCreateRequest,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_role("contractor")),
):
    resource = models.Resource(
        contractor_id=claims["sub"],
        resource_type=payload.resource_type,
        name=payload.name,
        notes=payload.notes,
        status="available",
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return _resource_to_response(resource)


@app.get("/v1/resources", response_model=list[schemas.ResourceResponse])
def list_resources(
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_role("contractor")),
):
    query = db.query(models.Resource).filter(models.Resource.contractor_id == claims["sub"])
    if status_filter is not None:
        if status_filter not in models.RESOURCE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "VALIDATION_ERROR",
                    "message": f"status must be one of {models.RESOURCE_STATUSES}",
                },
            )
        query = query.filter(models.Resource.status == status_filter)
    ordered = query.order_by(models.Resource.created_at.desc()).all()
    return [_resource_to_response(r) for r in ordered]


@app.get("/v1/resources/{resource_id}", response_model=schemas.ResourceResponse)
def get_resource(
    resource_id: uuid.UUID,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_role("contractor")),
):
    resource = db.query(models.Resource).filter(models.Resource.id == str(resource_id)).first()
    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND", "message": "No resource with this ID exists."},
        )
    if resource.contractor_id != claims["sub"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "You can only view your own resources."},
        )
    return _resource_to_response(resource)


@app.patch("/v1/resources/{resource_id}", response_model=schemas.ResourceResponse)
def update_resource(
    resource_id: uuid.UUID,
    payload: schemas.ResourceUpdateRequest,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_role("contractor")),
):
    resource = db.query(models.Resource).filter(models.Resource.id == str(resource_id)).first()
    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND", "message": "No resource with this ID exists."},
        )
    if resource.contractor_id != claims["sub"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "You can only edit your own resources."},
        )

    if payload.status is not None:
        resource.status = payload.status
    if payload.name is not None:
        resource.name = payload.name
    if payload.notes is not None:
        resource.notes = payload.notes

    db.commit()
    db.refresh(resource)
    return _resource_to_response(resource)
