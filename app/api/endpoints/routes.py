from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.database import get_db
from app.models.domain import Route, RouteStop
from app.schemas.domain import RouteBase, RouteWithStops, RouteStopBase

router = APIRouter()

@router.get("/search", response_model=List[RouteBase])
def search_routes(
    origin: Optional[str] = None, 
    destination: Optional[str] = None, 
    active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Route)
    if origin:
        query = query.filter(Route.origin.ilike(f"%{origin}%"))
    if destination:
        query = query.filter(Route.destination.ilike(f"%{destination}%"))
    if active is not None:
        query = query.filter(Route.active == active)
    return query.all()

@router.get("/{route_id}", response_model=RouteWithStops)
def get_route(route_id: str, db: Session = Depends(get_db)):
    route = db.query(Route).filter(Route.route_id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    return route

@router.get("/{route_id}/stops", response_model=List[RouteStopBase])
def get_route_stops(route_id: str, db: Session = Depends(get_db)):
    stops = db.query(RouteStop).filter(RouteStop.route_id == route_id).order_by(RouteStop.stop_sequence).all()
    return stops
