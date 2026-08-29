from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.db.database import get_db
from app.models.domain import TrafficEvent
from app.schemas.domain import TrafficEventBase

router = APIRouter()

@router.get("", response_model=List[TrafficEventBase])
def get_traffic_events(db: Session = Depends(get_db)):
    return db.query(TrafficEvent).filter(TrafficEvent.active == True).all()
