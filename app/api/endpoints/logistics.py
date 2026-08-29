from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas.domain import (
    LogisticsSearchRequest,
    LogisticsSearchResponse,
    ParcelBookRequest,
    ParcelBookResponse,
)
from app.services.matching import LogisticsMatchingService
from app.services.capacity import CapacityService
from app.models.domain import Schedule, Parcel, ParcelEvent
import uuid
import secrets

router = APIRouter()


@router.post("/search", response_model=LogisticsSearchResponse)
def search_logistics(request: LogisticsSearchRequest, db: Session = Depends(get_db)):
    """
    Search for available transport services matching logistics requirements.

    This is a READ-ONLY endpoint. It never modifies capacity.
    Results are informational only; actual capacity is re-checked on booking.
    """
    return LogisticsMatchingService.find_matches(db, request)


@router.post("/book", response_model=ParcelBookResponse)
def book_parcel(request: ParcelBookRequest, db: Session = Depends(get_db)):
    """
    Atomically validate, reserve capacity, and create a parcel booking.

    Validation steps (all performed server-side — client data is never trusted):
    1. Validate request fields (Pydantic)
    2. Verify schedule exists and is active
    3. Verify bus exists and is available
    4. Verify bus is parcel-enabled
    5. Verify route matches the schedule
    6. Re-check capacity on every required segment (atomically)
    7. Create the parcel record
    8. Create a tracking event
    9. Commit atomically

    Returns a structured booking confirmation with tracking ID.
    """
    try:
        # ── 2 & 3. Schedule validation ──────────────────────────────────────
        schedule = (
            db.query(Schedule)
            .filter(Schedule.schedule_id == request.schedule_id)
            .first()
        )
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        if not schedule.active:
            raise HTTPException(status_code=400, detail="Schedule is inactive")

        # ── 4 & 5. Route consistency ────────────────────────────────────────
        if schedule.route_id != request.route_id:
            raise HTTPException(
                status_code=400,
                detail=f"Schedule '{request.schedule_id}' belongs to route "
                       f"'{schedule.route_id}', not '{request.route_id}'.",
            )

        # ── 5 & 6. Bus validation ───────────────────────────────────────────
        bus = schedule.bus
        if not bus:
            raise HTTPException(status_code=400, detail="Bus not found for this schedule")

        if bus.status.upper() in {"UNAVAILABLE", "MAINTENANCE", "UNSAFE", "INACTIVE"}:
            raise HTTPException(
                status_code=400,
                detail=f"Bus '{bus.bus_number}' is unavailable (status: {bus.status})"
            )

        if not bus.parcel_enabled:
            raise HTTPException(
                status_code=400,
                detail=f"Bus '{bus.bus_number}' is not parcel-enabled"
            )

        # ── 7–11. Atomic capacity reservation ──────────────────────────────
        reservation_result = CapacityService.reserve_capacity(
            db=db,
            schedule_id=request.schedule_id,
            route_id=request.route_id,
            source_stop_name=request.source,
            destination_stop_name=request.destination,
            weight_kg=request.weight_kg,
        )

        if not reservation_result["success"]:
            raise HTTPException(status_code=400, detail=reservation_result["reason"])

        # ── 12. Create parcel (within same transaction) ─────────────────────
        tracking_id = f"KPM-{uuid.uuid4().hex[:8].upper()}"
        pickup_code = secrets.token_hex(3).upper()     # Not exposed in public responses
        delivery_code = secrets.token_hex(3).upper()   # Not exposed in public responses

        parcel = Parcel(
            tracking_id=tracking_id,
            sender_name=request.sender_name,
            sender_phone=request.sender_phone,
            receiver_name=request.receiver_name,
            receiver_phone=request.receiver_phone,
            source_stop=request.source,
            destination_stop=request.destination,
            weight_kg=request.weight_kg,
            volume_m3=request.volume_m3,
            parcel_type=request.parcel_type,
            status="RESERVED",
            assigned_schedule_id=request.schedule_id,
            pickup_verification_code=pickup_code,
            delivery_verification_code=delivery_code,
        )
        db.add(parcel)
        db.flush()  # Get parcel_id without committing

        # Create tracking event (same transaction)
        event = ParcelEvent(
            parcel_id=parcel.parcel_id,
            event_type="RESERVED",
            created_by="SYSTEM",
            notes=(
                f"Parcel booked on schedule {request.schedule_id}. "
                f"Capacity reserved on {reservation_result['segment_count']} segment(s)."
            ),
        )
        db.add(event)

        # ── Commit everything atomically ────────────────────────────────────
        db.commit()
        db.refresh(parcel)

        return {
            "status": "BOOKED",
            "tracking_id": parcel.tracking_id,
            "parcel_id": parcel.parcel_id,
            "schedule_id": schedule.schedule_id,
            "bus_number": bus.bus_number,
            "source": parcel.source_stop,
            "destination": parcel.destination_stop,
            "weight_kg": parcel.weight_kg,
            "departure_time": schedule.departure_time,
            "arrival_time": schedule.arrival_time,
            "capacity_reserved": {
                "segment_count": reservation_result["segment_count"],
                "weight_kg": reservation_result["weight_kg"],
            },
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal error during booking: {exc}")
