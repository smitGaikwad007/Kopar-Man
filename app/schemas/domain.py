from pydantic import BaseModel, Field, model_validator
from typing import List, Optional
from datetime import datetime
from enum import Enum

class DataSourceSchema(str, Enum):
    OFFICIAL = "OFFICIAL"
    OPERATOR = "OPERATOR"
    VERIFIED_LOCAL = "VERIFIED_LOCAL"
    SIMULATION = "SIMULATION"
    DEMO = "DEMO"

class RouteStopBase(BaseModel):
    stop_id: str
    stop_sequence: int
    stop_name: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    class Config:
        from_attributes = True

class RouteBase(BaseModel):
    route_id: str
    route_name: str
    origin: str
    destination: str
    active: bool
    data_source: DataSourceSchema
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None

    class Config:
        from_attributes = True

class RouteWithStops(RouteBase):
    route_stops: List[RouteStopBase] = []

class BusBase(BaseModel):
    bus_id: str
    bus_number: str
    service_type: str
    operator: str
    status: str
    parcel_enabled: bool
    data_source: DataSourceSchema
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None

    class Config:
        from_attributes = True

class ScheduleBase(BaseModel):
    schedule_id: str
    bus_id: str
    route_id: str
    service_date: str
    departure_time: str
    arrival_time: str
    active: bool
    data_source: DataSourceSchema
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None

    class Config:
        from_attributes = True

class ParcelEventBase(BaseModel):
    event_id: str
    event_type: str
    timestamp: datetime
    location: Optional[str] = None
    notes: Optional[str] = None
    created_by: str

    class Config:
        from_attributes = True

class ParcelBase(BaseModel):
    parcel_id: str
    tracking_id: str
    sender_name: str
    sender_phone: str
    receiver_name: str
    receiver_phone: str
    source_stop: str
    destination_stop: str
    weight_kg: float
    volume_m3: Optional[float] = None
    parcel_type: str
    status: str
    assigned_schedule_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ParcelWithEvents(ParcelBase):
    events: List[ParcelEventBase] = []

class ParcelCreate(BaseModel):
    sender_name: str
    sender_phone: str
    receiver_name: str
    receiver_phone: str
    source_stop: str
    destination_stop: str
    weight_kg: float
    volume_m3: Optional[float] = None
    parcel_type: str

class ParcelEventCreate(BaseModel):
    event_type: str
    location: Optional[str] = None
    notes: Optional[str] = None
    created_by: str

class LogisticsSearchRequest(BaseModel):
    source: str = Field(..., min_length=1)
    destination: str = Field(..., min_length=1)
    date: str
    time: Optional[str] = None
    weight_kg: Optional[float] = Field(None, gt=0)
    item_type: Optional[str] = None

    @model_validator(mode='after')
    def check_source_dest(self):
        if self.source.lower() == self.destination.lower():
            raise ValueError('Source and destination cannot be the same')
        return self

class LogisticsRecommendation(BaseModel):
    bus_id: str
    bus_number: str
    schedule_id: str
    route_id: str
    departure_time: str
    arrival_time: str
    available_capacity_kg: float
    score: int
    reasons: List[str]

class LogisticsSearchResponse(BaseModel):
    request: dict
    status: str
    recommendations: List[LogisticsRecommendation] = []
    reason: Optional[str] = None

class ParcelBookRequest(BaseModel):
    schedule_id: str
    route_id: str
    source: str = Field(..., min_length=1)
    destination: str = Field(..., min_length=1)
    weight_kg: float = Field(..., gt=0)
    sender_name: str
    sender_phone: str
    receiver_name: str
    receiver_phone: str
    parcel_type: str
    volume_m3: Optional[float] = None

class CapacityReservedResponse(BaseModel):
    segment_count: int
    weight_kg: float

class ParcelBookResponse(BaseModel):
    status: str
    tracking_id: str
    parcel_id: str
    schedule_id: str
    bus_number: str
    source: str
    destination: str
    weight_kg: float
    departure_time: str
    arrival_time: str
    capacity_reserved: CapacityReservedResponse

class TrafficEventBase(BaseModel):
    traffic_event_id: str
    location: str
    severity: str
    detected_at: datetime
    source: str
    description: str
    active: bool

    class Config:
        from_attributes = True
