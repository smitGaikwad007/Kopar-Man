from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.database import get_db
from app.models.domain import Schedule
from app.schemas.domain import ScheduleBase

router = APIRouter()

@router.get("/search", response_model=List[ScheduleBase])
def search_schedules(
    route_id: Optional[str] = None, 
    date: Optional[str] = None, 
    time: Optional[str] = None,
    active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Schedule)
    if route_id:
        query = query.filter(Schedule.route_id == route_id)
    if date:
        query = query.filter(Schedule.service_date == date)
    if time:
        query = query.filter(Schedule.departure_time >= time)
    if active is not None:
        query = query.filter(Schedule.active == active)
    return query.all()
