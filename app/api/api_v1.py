from fastapi import APIRouter
from app.api.endpoints import health, routes, buses, schedules, parcels, logistics, traffic, admin

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(routes.router, prefix="/routes", tags=["Routes"])
api_router.include_router(buses.router, prefix="/buses", tags=["Buses"])
api_router.include_router(schedules.router, prefix="/schedules", tags=["Schedules"])
api_router.include_router(parcels.router, prefix="/parcels", tags=["Parcels"])
api_router.include_router(logistics.router, prefix="/logistics", tags=["Logistics"])
api_router.include_router(traffic.router, prefix="/traffic", tags=["Traffic"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
