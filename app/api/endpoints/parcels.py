from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List
from app.db.database import get_db
from app.models.domain import Parcel, ParcelEvent, Schedule
from app.schemas.domain import ParcelBase, ParcelWithEvents, ParcelCreate, ParcelEventBase, ParcelEventCreate
from app.services.capacity import CapacityService
import uuid

router = APIRouter()

# Valid state transitions for the parcel state machine
ALLOWED_TRANSITIONS = {
    "CREATED":   ["RESERVED", "CANCELLED"],
    "RESERVED":  ["CONFIRMED", "CANCELLED"],
    "CONFIRMED": ["RECEIVED", "CANCELLED"],
    "RECEIVED":  ["LOADED", "CANCELLED"],
    "LOADED":    ["IN_TRANSIT", "EXCEPTION"],
    "IN_TRANSIT":["ARRIVED", "EXCEPTION"],
    "ARRIVED":   ["DELIVERED", "EXCEPTION"],
    "DELIVERED": [],   # Terminal – cannot be cancelled or modified
    "CANCELLED": [],   # Terminal – cannot be revived
    "EXCEPTION": ["CANCELLED"],
}

# States that hold reserved capacity and need it released on cancel
CAPACITY_HOLDING_STATES = {"RESERVED", "CONFIRMED", "RECEIVED"}

# States from which cancellation is allowed
CANCELLABLE_STATES = {"CREATED", "RESERVED", "CONFIRMED", "RECEIVED"}


def _release_parcel_capacity(db: Session, parcel: Parcel) -> None:
    """Release reserved capacity for a parcel if it has an assigned schedule."""
    if not parcel.assigned_schedule_id:
        return
    schedule = db.query(Schedule).filter_by(schedule_id=parcel.assigned_schedule_id).first()
    if schedule:
        CapacityService.release_capacity(
            db=db,
            schedule_id=parcel.assigned_schedule_id,
            route_id=schedule.route_id,
            source_stop_name=parcel.source_stop,
            destination_stop_name=parcel.destination_stop,
            weight_kg=parcel.weight_kg
        )


@router.post("", response_model=ParcelBase)
def create_parcel(parcel: ParcelCreate, db: Session = Depends(get_db)):
    """
    Legacy manual creation without capacity reservation.
    Prefer POST /api/logistics/book for production use.
    """
    new_parcel = Parcel(
        tracking_id=f"KPM-{uuid.uuid4().hex[:8].upper()}",
        sender_name=parcel.sender_name,
        sender_phone=parcel.sender_phone,
        receiver_name=parcel.receiver_name,
        receiver_phone=parcel.receiver_phone,
        source_stop=parcel.source_stop,
        destination_stop=parcel.destination_stop,
        weight_kg=parcel.weight_kg,
        volume_m3=parcel.volume_m3,
        parcel_type=parcel.parcel_type,
        status="CREATED"
    )
    db.add(new_parcel)
    db.flush()

    event = ParcelEvent(
        parcel_id=new_parcel.parcel_id,
        event_type="CREATED",
        created_by="SYSTEM",
        notes="Parcel created without capacity reservation"
    )
    db.add(event)
    db.commit()
    db.refresh(new_parcel)
    return new_parcel


@router.get("/track/{tracking_id}", response_model=ParcelWithEvents)
def track_parcel_by_tracking_id(tracking_id: str, db: Session = Depends(get_db)):
    """Lookup parcel by human-readable tracking ID (e.g. KPM-XXXXXXXX). Used by WhatsApp bot."""
    parcel = db.query(Parcel).filter(Parcel.tracking_id == tracking_id).first()
    if not parcel:
        raise HTTPException(status_code=404, detail=f"No parcel found with tracking ID: {tracking_id}")
    return parcel


@router.get("/{parcel_id}", response_model=ParcelWithEvents)
def get_parcel(parcel_id: str, db: Session = Depends(get_db)):
    """Get full parcel details by internal parcel_id."""
    parcel = db.query(Parcel).filter(Parcel.parcel_id == parcel_id).first()
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    return parcel


@router.get("/{parcel_id}/tracking", response_model=List[ParcelEventBase])
def get_parcel_tracking_events(parcel_id: str, db: Session = Depends(get_db)):
    """Return the chronological event trail for a parcel."""
    parcel = db.query(Parcel).filter(Parcel.parcel_id == parcel_id).first()
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    events = (
        db.query(ParcelEvent)
        .filter(ParcelEvent.parcel_id == parcel_id)
        .order_by(ParcelEvent.timestamp)
        .all()
    )
    return events


@router.post("/{parcel_id}/events", response_model=ParcelEventBase)
def add_parcel_event(parcel_id: str, event: ParcelEventCreate, db: Session = Depends(get_db)):
    """
    Advance the parcel state machine.
    Enforces valid transitions. Automatically releases capacity on DELIVERED.
    Note: for cancellation use POST /{parcel_id}/cancel instead.
    """
    try:
        parcel = db.query(Parcel).filter(Parcel.parcel_id == parcel_id).first()
        if not parcel:
            raise HTTPException(status_code=404, detail="Parcel not found")

        allowed = ALLOWED_TRANSITIONS.get(parcel.status, [])
        if event.event_type not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid state transition: {parcel.status} → {event.event_type}. "
                       f"Allowed: {allowed}"
            )

        # Release capacity when delivery is confirmed
        if event.event_type == "DELIVERED" and parcel.status in CAPACITY_HOLDING_STATES | {"LOADED", "IN_TRANSIT", "ARRIVED"}:
            _release_parcel_capacity(db, parcel)

        new_event = ParcelEvent(
            parcel_id=parcel_id,
            event_type=event.event_type,
            location=event.location,
            notes=event.notes,
            created_by=event.created_by
        )
        parcel.status = event.event_type

        db.add(new_event)
        db.commit()
        db.refresh(new_event)
        return new_event

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal error during state transition")


@router.post("/{parcel_id}/cancel")
def cancel_parcel(
    parcel_id: str,
    reason: str = Body(embed=True),
    db: Session = Depends(get_db)
):
    """
    Cancel a parcel. Only allowed before LOADED.
    Releases reserved capacity if appropriate.
    Creates a CANCELLED tracking event.
    """
    try:
        parcel = db.query(Parcel).filter(Parcel.parcel_id == parcel_id).first()
        if not parcel:
            raise HTTPException(status_code=404, detail="Parcel not found")

        if parcel.status not in CANCELLABLE_STATES:
            raise HTTPException(
                status_code=400,
                detail=f"Parcel in state '{parcel.status}' cannot be cancelled. "
                       f"Cancellable states: {sorted(CANCELLABLE_STATES)}"
            )

        # Release reserved capacity for pre-loading cancellations
        if parcel.status in CAPACITY_HOLDING_STATES:
            _release_parcel_capacity(db, parcel)

        parcel.status = "CANCELLED"

        event = ParcelEvent(
            parcel_id=parcel.parcel_id,
            event_type="CANCELLED",
            created_by="SYSTEM",
            notes=reason
        )
        db.add(event)
        db.commit()

        return {
            "status": "success",
            "parcel_id": parcel_id,
            "message": "Parcel cancelled and capacity released"
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal error during cancellation")
