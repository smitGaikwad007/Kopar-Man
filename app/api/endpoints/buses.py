from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.database import get_db
from app.models.domain import Bus
from app.schemas.domain import BusBase

router = APIRouter()

@router.get("/search", response_model=List[BusBase])
def search_buses(
    bus_number: Optional[str] = None, 
    parcel_enabled: Optional[bool] = None, 
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Bus)
    if bus_number:
        query = query.filter(Bus.bus_number.ilike(f"%{bus_number}%"))
    if parcel_enabled is not None:
        query = query.filter(Bus.parcel_enabled == parcel_enabled)
    if status:
        query = query.filter(Bus.status.ilike(status))
    return query.all()

@router.get("/{bus_id}", response_model=BusBase)
def get_bus(bus_id: str, db: Session = Depends(get_db)):
    bus = db.query(Bus).filter(Bus.bus_id == bus_id).first()
    if not bus:
        raise HTTPException(status_code=404, detail="Bus not found")
    return bus
