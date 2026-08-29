from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from app.db.database import get_db
from app.services.timetable import search_timetable

router = APIRouter()


class DepartureGroup(BaseModel):
    destination: str
    departures: List[str]
    data_source: str
    source_doc: Optional[str] = None
    source_name: Optional[str] = None


class TimetableSearchResponse(BaseModel):
    origin: str
    destination_filter: Optional[str] = None
    period_filter: Optional[str] = None
    after_time_filter: Optional[str] = None
    result_count: int
    destinations: List[DepartureGroup]
    note: str


@router.get("/search", response_model=TimetableSearchResponse)
def search_timetable_api(
    origin: str = Query(..., description="Origin bus stand, e.g. 'Kopargaon'"),
    destination: Optional[str] = Query(None, description="Filter by destination, e.g. 'Shirdi'"),
    period: Optional[str] = Query(
        None,
        description="Time-of-day filter: morning (05–12), afternoon (12–17), evening (17–23), night (23–05)"
    ),
    after_time: Optional[str] = Query(None, description="Only show buses at or after HH:MM"),
    db: Session = Depends(get_db),
):
    """
    Query the authenticated timetable for buses departing from ``origin``.

    - Optionally filter by ``destination``, time-of-day ``period``, or ``after_time``.
    - Returns departure times grouped by destination.
    - Results carry **OFFICIAL** data source label from the Kopargaon Bus Stand Timetable.
    - These services are **not** parcel-capable; use `/api/logistics/search` for parcel transport.

    Example:
    ```
    GET /api/timetable/search?origin=Kopargaon&destination=Shirdi
    ```
    """
    if period and period not in ("morning", "afternoon", "evening", "night"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="period must be one of: morning, afternoon, evening, night",
        )

    result = search_timetable(
        db=db,
        origin=origin,
        destination=destination,
        period=period,
        after_time=after_time,
    )

    if result["result_count"] == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No timetable entries found from '{origin}'"
            + (f" to '{destination}'" if destination else "")
            + (f" in period '{period}'" if period else ""),
        )

    return result
