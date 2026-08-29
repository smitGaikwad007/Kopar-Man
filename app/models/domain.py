from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from app.db.database import Base
from datetime import datetime
import enum
import uuid

def generate_uuid():
    return str(uuid.uuid4())

class DataSource(str, enum.Enum):
    OFFICIAL = "OFFICIAL"
    OPERATOR = "OPERATOR"
    VERIFIED_LOCAL = "VERIFIED_LOCAL"
    SIMULATION = "SIMULATION"
    DEMO = "DEMO"
    EXTERNAL_PROVIDER = "EXTERNAL_PROVIDER"
    MANUAL = "MANUAL"

class Bus(Base):
    __tablename__ = "buses"
    bus_id = Column(String, primary_key=True, default=generate_uuid)
    bus_number = Column(String, unique=True, index=True)
    service_type = Column(String)
    operator = Column(String)
    status = Column(String)
    parcel_enabled = Column(Boolean, default=False)
    data_source = Column(Enum(DataSource), default=DataSource.DEMO)
    valid_from = Column(DateTime, nullable=True)
    valid_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    schedules = relationship("Schedule", back_populates="bus")

class Route(Base):
    __tablename__ = "routes"
    route_id = Column(String, primary_key=True, default=generate_uuid)
    route_name = Column(String, index=True)
    origin = Column(String)
    destination = Column(String)
    active = Column(Boolean, default=True)
    data_source = Column(Enum(DataSource), default=DataSource.DEMO)
    valid_from = Column(DateTime, nullable=True)
    valid_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    route_stops = relationship("RouteStop", back_populates="route", order_by="RouteStop.stop_sequence")
    schedules = relationship("Schedule", back_populates="route")
    segments = relationship("RouteSegment", back_populates="route")

class RouteStop(Base):
    __tablename__ = "route_stops"
    route_id = Column(String, ForeignKey("routes.route_id"), primary_key=True)
    stop_id = Column(String, primary_key=True, default=generate_uuid)
    stop_sequence = Column(Integer)
    stop_name = Column(String)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    route = relationship("Route", back_populates="route_stops")

class Schedule(Base):
    __tablename__ = "schedules"
    schedule_id = Column(String, primary_key=True, default=generate_uuid)
    bus_id = Column(String, ForeignKey("buses.bus_id"))
    route_id = Column(String, ForeignKey("routes.route_id"))
    service_date = Column(String) # e.g. YYYY-MM-DD or recurrence representation
    departure_time = Column(String) # HH:MM
    arrival_time = Column(String) # HH:MM
    active = Column(Boolean, default=True)
    data_source = Column(Enum(DataSource), default=DataSource.DEMO)
    valid_from = Column(DateTime, nullable=True)
    valid_until = Column(DateTime, nullable=True)

    bus = relationship("Bus", back_populates="schedules")
    route = relationship("Route", back_populates="schedules")

class RouteSegment(Base):
    __tablename__ = "route_segments"
    segment_id = Column(String, primary_key=True, default=generate_uuid)
    route_id = Column(String, ForeignKey("routes.route_id"))
    from_stop = Column(String)
    to_stop = Column(String)
    sequence = Column(Integer)

    route = relationship("Route", back_populates="segments")

class ParcelCapacity(Base):
    __tablename__ = "parcel_capacity"
    capacity_id = Column(String, primary_key=True, default=generate_uuid)
    bus_id = Column(String, ForeignKey("buses.bus_id"))
    schedule_id = Column(String, ForeignKey("schedules.schedule_id"), nullable=True)
    segment_id = Column(String, ForeignKey("route_segments.segment_id"))
    max_safe_parcel_capacity_kg = Column(Float)
    reserved_capacity_kg = Column(Float, default=0.0)
    data_source = Column(Enum(DataSource), default=DataSource.DEMO)
    capacity_status = Column(String)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def available_capacity_kg(self):
        return max(0.0, self.max_safe_parcel_capacity_kg - self.reserved_capacity_kg)

class ParcelEvent(Base):
    __tablename__ = "parcel_events"
    event_id = Column(String, primary_key=True, default=generate_uuid)
    parcel_id = Column(String, ForeignKey("parcels.parcel_id"))
    event_type = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    location = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_by = Column(String)

class Parcel(Base):
    __tablename__ = "parcels"
    parcel_id = Column(String, primary_key=True, default=generate_uuid)
    tracking_id = Column(String, unique=True, index=True)
    sender_name = Column(String)
    sender_phone = Column(String)
    receiver_name = Column(String)
    receiver_phone = Column(String)
    source_stop = Column(String)
    destination_stop = Column(String)
    weight_kg = Column(Float)
    volume_m3 = Column(Float, nullable=True)
    parcel_type = Column(String)
    status = Column(String)
    
    assigned_schedule_id = Column(String, ForeignKey("schedules.schedule_id"), nullable=True)
    pickup_verification_code = Column(String, nullable=True)
    delivery_verification_code = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    events = relationship("ParcelEvent", backref="parcel")
    schedule = relationship("Schedule", foreign_keys=[assigned_schedule_id])

class RuralShipment(Base):
    __tablename__ = "rural_shipments"
    shipment_id = Column(String, primary_key=True, default=generate_uuid)
    producer_name = Column(String)
    producer_phone = Column(String)
    commodity = Column(String)
    quantity = Column(Float)
    unit = Column(String)
    source = Column(String)
    destination = Column(String)
    preferred_date = Column(String)
    preferred_time = Column(String)
    status = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class TrafficEvent(Base):
    __tablename__ = "traffic_events"
    traffic_event_id = Column(String, primary_key=True, default=generate_uuid)
    location = Column(String)
    severity = Column(String)
    detected_at = Column(DateTime, default=datetime.utcnow)
    source = Column(String)
    description = Column(Text)
    active = Column(Boolean, default=True)


class TimetableDeparture(Base):
    """
    Represents a recurring timetable departure from an origin to a destination.

    This model exists specifically to store authenticated timetable information
    (origin, destination, departure_time) WITHOUT requiring bus identity, route
    segments, service dates, or parcel capacity — none of which are present in
    the authenticated Kopargaon Bus Stand Timetable source document.

    These records are NEVER considered parcel-capable by the matching engine.
    Parcel transport requires explicit ParcelCapacity records linked to a
    Schedule with a known bus and route.

    Uniqueness is enforced on (origin, destination, departure_time) to allow
    idempotent re-imports.
    """
    __tablename__ = "timetable_departures"

    departure_id = Column(String, primary_key=True, default=generate_uuid)
    origin = Column(String, nullable=False, index=True)
    destination = Column(String, nullable=False, index=True)
    departure_time = Column(String, nullable=False)   # HH:MM, 24-hour

    # Source trust and provenance metadata
    data_source = Column(Enum(DataSource), nullable=False, default=DataSource.OFFICIAL)
    source_doc = Column(String, nullable=True)         # e.g. "Kopargaon-Bus-Stand-Timetable.pdf"
    source_name = Column(String, nullable=True)        # human-readable name

    # Validity window (populated when the source specifies one; NULL = always valid)
    valid_from = Column(DateTime, nullable=True)
    valid_until = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

