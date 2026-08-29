from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.dialects import sqlite as sqlite_dialect
from app.models.domain import RouteStop, RouteSegment, ParcelCapacity
from typing import Dict, Any, List, Optional, Tuple


def _get_required_segments(
    db: Session, route_id: str, source_stop_name: str, destination_stop_name: str
) -> Tuple[Optional[List[RouteSegment]], Optional[str]]:
    """
    Return ordered RouteSegments that a shipment from source to destination would traverse.
    Returns (segments, None) on success or (None, error_message) on failure.
    """
    source_stop = (
        db.query(RouteStop)
        .filter(RouteStop.route_id == route_id, RouteStop.stop_name == source_stop_name)
        .first()
    )
    dest_stop = (
        db.query(RouteStop)
        .filter(RouteStop.route_id == route_id, RouteStop.stop_name == destination_stop_name)
        .first()
    )

    if not source_stop:
        return None, f"Source stop '{source_stop_name}' not found on route '{route_id}'."
    if not dest_stop:
        return None, f"Destination stop '{destination_stop_name}' not found on route '{route_id}'."
    if source_stop.stop_sequence >= dest_stop.stop_sequence:
        return None, f"Destination '{destination_stop_name}' must come after source '{source_stop_name}' on the route."

    segments = (
        db.query(RouteSegment)
        .filter(
            RouteSegment.route_id == route_id,
            RouteSegment.sequence >= source_stop.stop_sequence,
            RouteSegment.sequence < dest_stop.stop_sequence,
        )
        .order_by(RouteSegment.sequence)
        .all()
    )

    if not segments:
        return None, "No route segments found between source and destination."

    return segments, None


def _is_sqlite(db: Session) -> bool:
    """Detect whether the session is using SQLite (for FOR UPDATE compatibility)."""
    return "sqlite" in str(db.bind.dialect.name).lower()


class CapacityService:
    """
    Handles segment-aware parcel capacity: checking, reserving, and releasing.
    All mutating operations (reserve/release) MUST be called inside a database transaction.
    """

    @staticmethod
    def check_segment_capacity(
        db: Session,
        schedule_id: str,
        route_id: str,
        source_stop_name: str,
        destination_stop_name: str,
        requested_weight_kg: float,
    ) -> Dict[str, Any]:
        """
        Read-only capacity check. Does NOT modify the database.
        Use this in the search/matching pipeline only.
        """
        segments, error = _get_required_segments(db, route_id, source_stop_name, destination_stop_name)
        if error:
            return {"eligible": False, "reason": error, "segments_checked": 0, "available_capacity": 0.0}

        min_available = float("inf")
        limiting_segment = None

        for segment in segments:
            capacity = (
                db.query(ParcelCapacity)
                .filter(
                    ParcelCapacity.schedule_id == schedule_id,
                    ParcelCapacity.segment_id == segment.segment_id,
                )
                .first()
            )
            segment_avail = capacity.available_capacity_kg if capacity else 0.0

            if segment_avail < min_available:
                min_available = segment_avail
                limiting_segment = f"{segment.from_stop} → {segment.to_stop}"

        if min_available < requested_weight_kg:
            return {
                "eligible": False,
                "reason": f"Insufficient capacity on segment {limiting_segment}: "
                          f"{min_available:.1f} kg available, {requested_weight_kg:.1f} kg requested.",
                "segments_checked": len(segments),
                "limiting_segment": limiting_segment,
                "available_capacity": min_available,
            }

        return {
            "eligible": True,
            "reason": "Capacity available across all required segments.",
            "segments_checked": len(segments),
            "limiting_segment": limiting_segment,
            "available_capacity": min_available,
        }

    @staticmethod
    def reserve_capacity(
        db: Session,
        schedule_id: str,
        route_id: str,
        source_stop_name: str,
        destination_stop_name: str,
        weight_kg: float,
    ) -> Dict[str, Any]:
        """
        Atomically reserve capacity across all required segments.

        Concurrency strategy:
        - PostgreSQL: Uses SELECT … FOR UPDATE to lock capacity rows before checking
          and updating, preventing two concurrent requests from double-booking.
        - SQLite (test environment): FOR UPDATE is not supported and is silently skipped;
          Python-level sequential execution within a single process still prevents
          most races, but true concurrent multi-process oversubscription cannot be
          fully prevented in SQLite.

        Must be called within a database transaction. Caller is responsible for
        committing or rolling back.
        """
        segments, error = _get_required_segments(db, route_id, source_stop_name, destination_stop_name)
        if error:
            return {"success": False, "reason": error}

        segment_ids = [s.segment_id for s in segments]

        try:
            query = db.query(ParcelCapacity).filter(
                ParcelCapacity.schedule_id == schedule_id,
                ParcelCapacity.segment_id.in_(segment_ids),
            )

            # Use SELECT FOR UPDATE on PostgreSQL to prevent concurrent oversubscription
            if not _is_sqlite(db):
                query = query.with_for_update()

            capacities = query.all()

            if len(capacities) != len(segments):
                found_ids = {c.segment_id for c in capacities}
                missing = [sid for sid in segment_ids if sid not in found_ids]
                return {
                    "success": False,
                    "reason": f"Missing capacity records for segments: {missing}. "
                              "Ensure parcel_capacity is seeded for this schedule.",
                }

            # Verify capacity with locked rows
            for cap in capacities:
                if cap.available_capacity_kg < weight_kg:
                    seg = next(s for s in segments if s.segment_id == cap.segment_id)
                    return {
                        "success": False,
                        "reason": (
                            f"Insufficient capacity on segment {seg.from_stop} → {seg.to_stop}: "
                            f"{cap.available_capacity_kg:.1f} kg available, {weight_kg:.1f} kg requested."
                        ),
                    }

            # All segments have capacity — reserve it
            for cap in capacities:
                cap.reserved_capacity_kg += weight_kg

            db.flush()  # flush within transaction; caller commits

            return {
                "success": True,
                "segment_count": len(segments),
                "weight_kg": weight_kg,
            }

        except SQLAlchemyError as exc:
            return {"success": False, "reason": f"Database error during capacity reservation: {exc}"}

    @staticmethod
    def release_capacity(
        db: Session,
        schedule_id: str,
        route_id: str,
        source_stop_name: str,
        destination_stop_name: str,
        weight_kg: float,
    ) -> Dict[str, Any]:
        """
        Safely release reserved capacity across all required segments.
        Clamps to zero — reserved_capacity_kg will never go negative.
        """
        segments, error = _get_required_segments(db, route_id, source_stop_name, destination_stop_name)
        if error:
            return {"success": False, "reason": error}

        segment_ids = [s.segment_id for s in segments]

        try:
            query = db.query(ParcelCapacity).filter(
                ParcelCapacity.schedule_id == schedule_id,
                ParcelCapacity.segment_id.in_(segment_ids),
            )
            if not _is_sqlite(db):
                query = query.with_for_update()

            capacities = query.all()

            for cap in capacities:
                cap.reserved_capacity_kg = max(0.0, cap.reserved_capacity_kg - weight_kg)

            db.flush()
            return {"success": True, "segments_released": len(capacities)}

        except SQLAlchemyError as exc:
            return {"success": False, "reason": f"Database error during capacity release: {exc}"}
