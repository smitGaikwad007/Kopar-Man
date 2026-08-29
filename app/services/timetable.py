"""
Timetable Service — Kopar-Man

Handles importing, validating, and querying recurring bus timetable information.

Key design principle:
    TimetableDeparture records are intentionally separated from the Schedule,
    Bus, Route, and ParcelCapacity tables. They represent WHAT is known from an
    authenticated timetable source: origin, destination, and departure time.

    They deliberately do NOT contain:
      - bus identity / registration
      - route segments or intermediate stops
      - arrival times
      - parcel capacity or parcel eligibility

    The logistics matching engine (LogisticsMatchingService) uses the Schedule
    table for parcel matching. It never reads TimetableDeparture records.
    Timetable-only entries are therefore structurally incapable of appearing
    as parcel recommendations — they are invisible to the parcel pipeline.
"""

import re
from typing import List, Dict, Any, Optional
from collections import defaultdict
from sqlalchemy.orm import Session
from app.models.domain import TimetableDeparture, DataSource

# ── Constants ──────────────────────────────────────────────────────────────────

TIME_RE = re.compile(r"^\d{2}:\d{2}$")  # strict HH:MM 24-hour

TIME_PERIODS = {
    "morning":   (5,  12),   # 05:00 – 11:59
    "afternoon": (12, 17),   # 12:00 – 16:59
    "evening":   (17, 23),   # 17:00 – 22:59
    "night":     (23, 5),    # 23:00 – 04:59  (wraps midnight)
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _normalize_time(raw: str) -> Optional[str]:
    """
    Convert any reasonably formatted time string to strict HH:MM.
    Accepts '8:00', '08:00', '8:5' → '08:05'. Returns None if unparseable.
    """
    raw = raw.strip()
    parts = raw.split(":")
    if len(parts) != 2:
        return None
    try:
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            return None
        return f"{h:02d}:{m:02d}"
    except ValueError:
        return None


def _hour(time_str: str) -> int:
    return int(time_str.split(":")[0])


def _in_period(time_str: str, period: str) -> bool:
    if period not in TIME_PERIODS:
        return True  # no filter
    start, end = TIME_PERIODS[period]
    h = _hour(time_str)
    if start < end:
        return start <= h < end
    else:  # wraps midnight
        return h >= start or h < end


# ── Validation ─────────────────────────────────────────────────────────────────

def validate_timetable_rows(rows: List[Dict[str, Any]]) -> List[str]:
    """
    Validate a list of timetable row dicts (as read from CSV).
    Returns a list of error strings; empty list = valid.
    """
    errors: List[str] = []
    seen: set = set()

    for i, row in enumerate(rows, start=2):  # start=2 → CSV line number (1=header)
        origin = (row.get("origin") or "").strip()
        destination = (row.get("destination") or "").strip()
        departure_time_raw = (row.get("departure_time") or "").strip()
        data_source = (row.get("data_source") or "").strip()

        if not origin:
            errors.append(f"Row {i}: origin is empty.")
        if not destination:
            errors.append(f"Row {i}: destination is empty.")

        norm_time = _normalize_time(departure_time_raw)
        if norm_time is None:
            errors.append(f"Row {i}: invalid departure_time '{departure_time_raw}' for {destination}.")

        valid_sources = {s.value for s in DataSource}
        if data_source not in valid_sources:
            errors.append(f"Row {i}: invalid data_source '{data_source}'.")

        if data_source != "OFFICIAL":
            errors.append(
                f"Row {i}: timetable records must have data_source=OFFICIAL, got '{data_source}'."
            )

        if origin and destination and norm_time:
            key = (origin.lower(), destination.lower(), norm_time)
            if key in seen:
                errors.append(
                    f"Row {i}: duplicate entry origin='{origin}' destination='{destination}' "
                    f"departure_time='{norm_time}'."
                )
            seen.add(key)

    return errors


# ── Import / Upsert ────────────────────────────────────────────────────────────

def upsert_timetable_rows(
    db: Session,
    rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Idempotently upsert timetable rows into the database.

    Uniqueness is keyed on (origin, destination, departure_time).
    Existing records matching that key are updated (source metadata refreshed).
    New records are inserted.

    Caller is responsible for committing or rolling back.
    """
    inserted = 0
    updated = 0

    for row in rows:
        origin = row["origin"].strip()
        destination = row["destination"].strip()
        departure_time = _normalize_time(row["departure_time"].strip())
        data_source = row.get("data_source", "OFFICIAL").strip()
        source_doc = (row.get("source_doc") or "").strip() or None
        source_name = (row.get("source_name") or "").strip() or None

        existing = (
            db.query(TimetableDeparture)
            .filter(
                TimetableDeparture.origin == origin,
                TimetableDeparture.destination == destination,
                TimetableDeparture.departure_time == departure_time,
            )
            .first()
        )

        if existing:
            # Refresh provenance metadata (idempotent update)
            existing.data_source = DataSource(data_source)
            existing.source_doc = source_doc
            existing.source_name = source_name
            updated += 1
        else:
            db.add(
                TimetableDeparture(
                    origin=origin,
                    destination=destination,
                    departure_time=departure_time,
                    data_source=DataSource(data_source),
                    source_doc=source_doc,
                    source_name=source_name,
                )
            )
            inserted += 1

    db.flush()
    return {"inserted": inserted, "updated": updated, "total": inserted + updated}


# ── Query ──────────────────────────────────────────────────────────────────────

def search_timetable(
    db: Session,
    origin: str,
    destination: Optional[str] = None,
    period: Optional[str] = None,
    after_time: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Search the timetable for departures from ``origin``.

    Parameters
    ----------
    origin:
        The departure city (case-insensitive prefix or exact match).
    destination:
        Filter to a specific destination (case-insensitive, exact match).
    period:
        One of 'morning', 'afternoon', 'evening', 'night'.  Applied on top of
        any after_time filter.
    after_time:
        Only return departures at or after this HH:MM time (useful for
        "what buses leave after 14:00?").

    Returns a dict ready to be serialised as the API response.
    """
    query = db.query(TimetableDeparture).filter(
        TimetableDeparture.origin.ilike(f"%{origin}%")
    )

    if destination:
        query = query.filter(
            TimetableDeparture.destination.ilike(f"%{destination}%")
        )

    rows: List[TimetableDeparture] = query.order_by(
        TimetableDeparture.destination,
        TimetableDeparture.departure_time,
    ).all()

    # Apply time filters in Python (HH:MM strings sort lexicographically)
    if after_time:
        norm = _normalize_time(after_time) or after_time
        rows = [r for r in rows if r.departure_time >= norm]

    if period:
        rows = [r for r in rows if _in_period(r.departure_time, period)]

    # Group by destination for a clean WhatsApp-friendly response
    grouped: Dict[str, List[str]] = defaultdict(list)
    meta: Dict[str, Any] = {}  # capture per-destination source metadata

    for r in rows:
        grouped[r.destination].append(r.departure_time)
        if r.destination not in meta:
            meta[r.destination] = {
                "data_source": r.data_source.value,
                "source_doc": r.source_doc,
                "source_name": r.source_name,
            }

    destinations_found = [
        {
            "destination": dest,
            "departures": times,
            "data_source": meta[dest]["data_source"],
            "source_doc": meta[dest]["source_doc"],
            "source_name": meta[dest]["source_name"],
        }
        for dest, times in sorted(grouped.items())
    ]

    return {
        "origin": origin,
        "destination_filter": destination,
        "period_filter": period,
        "after_time_filter": after_time,
        "result_count": len(rows),
        "destinations": destinations_found,
        "note": (
            "These are authenticated timetable departures. "
            "Bus identity, intermediate stops, and arrival times are not available in this source. "
            "These services are NOT listed as parcel-capable."
        ),
    }
