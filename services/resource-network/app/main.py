import os
import uuid
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.deps import require_role
from app.geo import haversine_km

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
        lat=r.lat,
        lng=r.lng,
        hourly_rate=r.hourly_rate,
        vehicle_type=r.vehicle_type,
        created_at=r.created_at,
    )


def _service_area_to_response(a: models.ServiceArea) -> schemas.ServiceAreaResponse:
    return schemas.ServiceAreaResponse(
        area_id=a.id,
        name=a.name,
        district=a.district,
        state=a.state,
        center_lat=a.center_lat,
        center_lng=a.center_lng,
        radius_km=a.radius_km,
        estimated_water_depth_ft=a.estimated_water_depth_ft,
        confidence_band_ft=a.confidence_band_ft,
        source=a.source,
        updated_at=a.updated_at,
    )


def _booking_to_response(b: models.BookingRequest) -> schemas.BookingRequestResponse:
    return schemas.BookingRequestResponse(
        booking_id=b.id,
        resource_id=b.resource_id,
        owner_id=b.owner_id,
        contractor_id=b.contractor_id,
        job_id=b.job_id,
        status=b.status,
        message=b.message,
        created_at=b.created_at,
        responded_at=b.responded_at,
    )


# ---------- resources (owned by resource_owner) ----------


@app.post("/v1/resources", response_model=schemas.ResourceResponse, status_code=201)
def create_resource(
    payload: schemas.ResourceCreateRequest,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_role("resource_owner")),
):
    resource = models.Resource(
        owner_id=claims["sub"],
        resource_type=payload.resource_type,
        name=payload.name,
        notes=payload.notes,
        lat=payload.lat,
        lng=payload.lng,
        hourly_rate=payload.hourly_rate,
        vehicle_type=payload.vehicle_type,
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
    claims: dict = Depends(require_role("resource_owner")),
):
    """A resource_owner's own fleet, for their dashboard. This is NOT the
    marketplace search - see POST /v1/resources/match for that (cross-
    owner, contractor-facing)."""
    query = db.query(models.Resource).filter(models.Resource.owner_id == claims["sub"])
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
    claims: dict = Depends(require_role("resource_owner")),
):
    resource = db.query(models.Resource).filter(models.Resource.id == str(resource_id)).first()
    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND", "message": "No resource with this ID exists."},
        )
    if resource.owner_id != claims["sub"]:
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
    claims: dict = Depends(require_role("resource_owner")),
):
    resource = db.query(models.Resource).filter(models.Resource.id == str(resource_id)).first()
    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND", "message": "No resource with this ID exists."},
        )
    if resource.owner_id != claims["sub"]:
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
    if payload.lat is not None:
        resource.lat = payload.lat
    if payload.lng is not None:
        resource.lng = payload.lng
    if payload.hourly_rate is not None:
        resource.hourly_rate = payload.hourly_rate
    if payload.vehicle_type is not None:
        resource.vehicle_type = payload.vehicle_type

    db.commit()
    db.refresh(resource)
    return _resource_to_response(resource)


# ---------- nearest-resource search (marketplace, cross-owner) ----------


@app.post("/v1/resources/match", response_model=list[schemas.ResourceMatchResult])
def match_resources(
    payload: schemas.ResourceMatchRequest,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_role("contractor")),
):
    """Contractor-facing marketplace search: nearest AVAILABLE resources
    across ALL resource_owners, ranked by distance (Google-Maps-style).
    This is the actual marketplace lookup - contractors don't own these
    resources, they request to book them (see POST /v1/bookings)."""
    query = db.query(models.Resource).filter(
        models.Resource.status == "available",
        models.Resource.lat.isnot(None),
        models.Resource.lng.isnot(None),
    )
    if payload.resource_type is not None:
        query = query.filter(models.Resource.resource_type == payload.resource_type)

    candidates = query.all()

    ranked = sorted(
        (
            schemas.ResourceMatchResult(
                resource_id=r.id,
                name=r.name,
                resource_type=r.resource_type,
                status=r.status,
                hourly_rate=r.hourly_rate,
                vehicle_type=r.vehicle_type,
                distance_km=round(haversine_km(payload.lat, payload.lng, r.lat, r.lng), 2),
            )
            for r in candidates
        ),
        key=lambda result: result.distance_km,
    )
    return ranked[: payload.max_results]


# ---------- booking requests (contractor requests, owner accepts/rejects) ----------


@app.post("/v1/bookings", response_model=schemas.BookingRequestResponse, status_code=201)
def create_booking_request(
    payload: schemas.BookingRequestCreate,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_role("contractor")),
):
    """Contractor requests to book a resource found via /v1/resources/match.
    The resource must currently be 'available' and have no other pending/
    accepted request against it - one active request per resource at a
    time, to prevent double-booking a rig two contractors both want."""
    resource = (
        db.query(models.Resource).filter(models.Resource.id == str(payload.resource_id)).first()
    )
    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RESOURCE_NOT_FOUND", "message": "No resource with this ID exists."},
        )
    if resource.status != "available":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "RESOURCE_NOT_AVAILABLE",
                "message": f"Resource status is '{resource.status}', not 'available'.",
            },
        )
    existing_active = (
        db.query(models.BookingRequest)
        .filter(
            models.BookingRequest.resource_id == str(payload.resource_id),
            models.BookingRequest.status.in_(["pending", "accepted"]),
        )
        .first()
    )
    if existing_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "RESOURCE_ALREADY_REQUESTED",
                "message": "This resource already has an active booking request.",
            },
        )

    booking = models.BookingRequest(
        resource_id=str(payload.resource_id),
        owner_id=resource.owner_id,
        contractor_id=claims["sub"],
        job_id=str(payload.job_id) if payload.job_id else None,
        message=payload.message,
        status="pending",
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return _booking_to_response(booking)


@app.get("/v1/bookings", response_model=list[schemas.BookingRequestResponse])
def list_bookings(
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_role("resource_owner", "contractor")),
):
    """Role-scoped: a resource_owner sees requests ON their resources;
    a contractor sees requests THEY made. Never both, regardless of role -
    the query filter is chosen by claims["role"], not a parameter the
    caller controls."""
    if claims["role"] == "resource_owner":
        query = db.query(models.BookingRequest).filter(
            models.BookingRequest.owner_id == claims["sub"]
        )
    else:
        query = db.query(models.BookingRequest).filter(
            models.BookingRequest.contractor_id == claims["sub"]
        )
    if status_filter is not None:
        if status_filter not in models.BOOKING_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "VALIDATION_ERROR",
                    "message": f"status must be one of {models.BOOKING_STATUSES}",
                },
            )
        query = query.filter(models.BookingRequest.status == status_filter)
    ordered = query.order_by(models.BookingRequest.created_at.desc()).all()
    return [_booking_to_response(b) for b in ordered]


def _respond_to_booking(
    booking_id: uuid.UUID, new_status: str, db: Session, claims: dict
) -> models.BookingRequest:
    booking = (
        db.query(models.BookingRequest)
        .filter(models.BookingRequest.id == str(booking_id))
        .first()
    )
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "BOOKING_NOT_FOUND",
                "message": "No booking request with this ID exists.",
            },
        )
    if booking.owner_id != claims["sub"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN",
                "message": "You can only respond to requests on your own resources.",
            },
        )
    if booking.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "BOOKING_ALREADY_RESOLVED",
                "message": (
                    f"This booking request is already '{booking.status}' "
                    "and cannot be changed."
                ),
            },
        )

    booking.status = new_status
    booking.responded_at = datetime.now(timezone.utc)

    if new_status == "accepted":
        resource = (
            db.query(models.Resource).filter(models.Resource.id == booking.resource_id).first()
        )
        # Guards against the resource having been made unavailable via
        # PATCH between the request being made and the owner accepting it
        # (e.g. the owner marked it in_use for something else in the
        # meantime) - accept must not silently reserve an unavailable
        # resource.
        if resource is None or resource.status != "available":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "RESOURCE_NO_LONGER_AVAILABLE",
                    "message": "This resource is no longer available and cannot be accepted.",
                },
            )
        resource.status = "reserved"

    db.commit()
    db.refresh(booking)
    return booking


@app.post("/v1/bookings/{booking_id}/accept", response_model=schemas.BookingRequestResponse)
def accept_booking(
    booking_id: uuid.UUID,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_role("resource_owner")),
):
    booking = _respond_to_booking(booking_id, "accepted", db, claims)
    return _booking_to_response(booking)


@app.post("/v1/bookings/{booking_id}/reject", response_model=schemas.BookingRequestResponse)
def reject_booking(
    booking_id: uuid.UUID,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_role("resource_owner")),
):
    booking = _respond_to_booking(booking_id, "rejected", db, claims)
    return _booking_to_response(booking)


# ---------- service areas (pilot water-depth reference data) ----------


@app.post("/v1/service-areas", response_model=schemas.ServiceAreaResponse, status_code=201)
def upsert_service_area(
    payload: schemas.ServiceAreaUpsertRequest,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_role("contractor", "admin")),
):
    """Upsert by (name, district) - posting the same area again updates it,
    same convention as quotation service's pricing-rules upsert."""
    existing = (
        db.query(models.ServiceArea)
        .filter(
            models.ServiceArea.name == payload.name,
            models.ServiceArea.district == payload.district,
        )
        .first()
    )
    if existing:
        existing.state = payload.state
        existing.center_lat = payload.center_lat
        existing.center_lng = payload.center_lng
        existing.radius_km = payload.radius_km
        existing.estimated_water_depth_ft = payload.estimated_water_depth_ft
        existing.confidence_band_ft = payload.confidence_band_ft
        db.commit()
        db.refresh(existing)
        return _service_area_to_response(existing)

    area = models.ServiceArea(
        name=payload.name,
        district=payload.district,
        state=payload.state,
        center_lat=payload.center_lat,
        center_lng=payload.center_lng,
        radius_km=payload.radius_km,
        estimated_water_depth_ft=payload.estimated_water_depth_ft,
        confidence_band_ft=payload.confidence_band_ft,
        source="contractor_estimate",
    )
    db.add(area)
    db.commit()
    db.refresh(area)
    return _service_area_to_response(area)


@app.get("/v1/service-areas", response_model=list[schemas.ServiceAreaResponse])
def list_service_areas(db: Session = Depends(get_db)):
    areas = db.query(models.ServiceArea).order_by(models.ServiceArea.name).all()
    return [_service_area_to_response(a) for a in areas]


@app.get("/v1/service-areas/lookup", response_model=schemas.ServiceAreaResponse)
def lookup_service_area(
    lat: float,
    lng: float,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_role("customer", "contractor", "admin")),
):
    """Find the nearest configured service area whose radius covers this
    point. 404 outside every configured area's radius - this is the
    expected outcome outside the pilot villages, not an error condition;
    callers (quotation service) should fall back to the contractor's flat
    assumed_depth_ft, not surface this 404 to the end user."""
    areas = db.query(models.ServiceArea).all()
    covering = []
    for area in areas:
        distance = haversine_km(lat, lng, area.center_lat, area.center_lng)
        if distance <= area.radius_km:
            covering.append((distance, area))

    if not covering:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NO_SERVICE_AREA_COVERAGE",
                "message": "No configured service area covers this point.",
            },
        )

    covering.sort(key=lambda pair: pair[0])
    nearest_area = covering[0][1]
    return _service_area_to_response(nearest_area)
