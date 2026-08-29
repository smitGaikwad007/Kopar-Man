import tempfile
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.database import Base, get_db
import app.models.domain as domain


from sqlalchemy.pool import StaticPool
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    # Seed DEMO data required for all tests
    db = TestingSessionLocal()
    
    # 1. Bus
    bus = domain.Bus(
        bus_id="bus_1",
        bus_number="MH-DEMO-1",
        service_type="EXPRESS",
        status="ACTIVE",
        parcel_enabled=True,
        data_source=domain.DataSource.DEMO
    )
    bus2 = domain.Bus(
        bus_id="bus_2_no_parcel",
        bus_number="MH-DEMO-2",
        service_type="EXPRESS",
        status="ACTIVE",
        parcel_enabled=False,
        data_source=domain.DataSource.DEMO
    )
    db.add_all([bus, bus2])
    
    # 2. Route (Kopargaon -> Shirdi -> Rahata)
    route = domain.Route(
        route_id="rt_1",
        route_name="Demo Route",
        origin="Kopargaon",
        destination="Rahata",
        active=True,
        data_source=domain.DataSource.DEMO
    )
    db.add(route)
    
    # 3. Route Stops
    stops = [
        domain.RouteStop(route_id="rt_1", stop_id="s1", stop_sequence=1, stop_name="Kopargaon"),
        domain.RouteStop(route_id="rt_1", stop_id="s2", stop_sequence=2, stop_name="Shirdi"),
        domain.RouteStop(route_id="rt_1", stop_id="s3", stop_sequence=3, stop_name="Rahata")
    ]
    db.add_all(stops)
    
    # 4. Route Segments
    seg1 = domain.RouteSegment(segment_id="seg1", route_id="rt_1", from_stop="Kopargaon", to_stop="Shirdi", sequence=1)
    seg2 = domain.RouteSegment(segment_id="seg2", route_id="rt_1", from_stop="Shirdi", to_stop="Rahata", sequence=2)
    db.add_all([seg1, seg2])
    
    # 5. Schedule for Bus 1
    sch = domain.Schedule(
        schedule_id="sch_1",
        bus_id="bus_1",
        route_id="rt_1",
        service_date="2026-09-01",
        departure_time="07:00",
        arrival_time="08:00",
        active=True,
        data_source=domain.DataSource.DEMO
    )
    db.add(sch)
    
    # Schedule for Bus 2 (no parcel)
    sch2 = domain.Schedule(
        schedule_id="sch_2",
        bus_id="bus_2_no_parcel",
        route_id="rt_1",
        service_date="2026-09-01",
        departure_time="08:00",
        arrival_time="09:00",
        active=True,
        data_source=domain.DataSource.DEMO
    )
    db.add(sch2)
    
    # 6. Parcel Capacity (for Bus 1)
    cap1 = domain.ParcelCapacity(
        capacity_id="cap1",
        bus_id="bus_1",
        schedule_id="sch_1",
        segment_id="seg1",
        max_safe_parcel_capacity_kg=100.0,
        reserved_capacity_kg=0.0
    )
    cap2 = domain.ParcelCapacity(
        capacity_id="cap2",
        bus_id="bus_1",
        schedule_id="sch_1",
        segment_id="seg2",
        max_safe_parcel_capacity_kg=100.0,
        reserved_capacity_kg=0.0
    )
    db.add_all([cap1, cap2])
    
    db.commit()
    yield

def test_1_direct_route_exists_capacity_sufficient():
    # TEST 1: Direct route exists and capacity is sufficient.
    payload = {
        "source": "Kopargaon",
        "destination": "Rahata",
        "date": "2026-09-01",
        "weight_kg": 50
    }
    response = client.post("/api/logistics/search", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "MATCH_FOUND"
    assert len(data["recommendations"]) >= 1
    rec = data["recommendations"][0]
    assert rec["available_capacity_kg"] == 100.0
    assert "Direct route match." in rec["reasons"]

def test_2_capacity_insufficient():
    # TEST 2: Capacity insufficient.
    payload = {
        "source": "Kopargaon",
        "destination": "Rahata",
        "date": "2026-09-01",
        "weight_kg": 150 # Exceeds 100 max
    }
    response = client.post("/api/logistics/search", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "NO_MATCH"
    assert "Eligible schedules found, but they lacked sufficient parcel capacity" in data["reason"]

def test_3_capacity_insufficient_second_segment():
    # TEST 3: Capacity sufficient on first segment but insufficient on second segment.
    db = TestingSessionLocal()
    cap2 = db.query(domain.ParcelCapacity).filter(domain.ParcelCapacity.capacity_id == "cap2").first()
    cap2.reserved_capacity_kg = 80.0 # Available becomes 20.0
    db.commit()
    db.close()
    
    payload = {
        "source": "Kopargaon",
        "destination": "Rahata",
        "date": "2026-09-01",
        "weight_kg": 50 # Needs 50, but seg2 only has 20
    }
    response = client.post("/api/logistics/search", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "NO_MATCH"

def test_4_bus_not_parcel_enabled():
    # TEST 4: Bus is not parcel-enabled.
    # We will search for time 08:00, where only bus_2 (no parcel) operates.
    payload = {
        "source": "Kopargaon",
        "destination": "Rahata",
        "date": "2026-09-01",
        "time": "08:00",
        "weight_kg": 50
    }
    response = client.post("/api/logistics/search", json=payload)
    data = response.json()
    # Bus 1 is at 07:00 (within 1 hr), Bus 2 is at 08:00
    # Bus 2 should be excluded completely. Bus 1 might match.
    recs = data.get("recommendations", [])
    for rec in recs:
        assert rec["bus_id"] != "bus_2_no_parcel"

def test_5_source_after_destination():
    # TEST 5: Source occurs after destination in route order.
    payload = {
        "source": "Rahata", # sequence 3
        "destination": "Kopargaon", # sequence 1
        "date": "2026-09-01",
        "weight_kg": 50
    }
    response = client.post("/api/logistics/search", json=payload)
    data = response.json()
    assert data["status"] == "NO_MATCH"
    assert "No active route found" in data["reason"]

def test_6_search_does_not_modify_capacity():
    # TEST 6: Search does not modify reserved capacity.
    payload = {
        "source": "Kopargaon",
        "destination": "Rahata",
        "date": "2026-09-01",
        "weight_kg": 50
    }
    client.post("/api/logistics/search", json=payload)
    
    db = TestingSessionLocal()
    cap1 = db.query(domain.ParcelCapacity).filter(domain.ParcelCapacity.capacity_id == "cap1").first()
    assert cap1.reserved_capacity_kg == 0.0 # Unchanged
    db.close()

def test_7_traffic_event_affects_ranking():
    # TEST 7: Traffic event affects ranking/warning when traffic data exists.
    db = TestingSessionLocal()
    te = domain.TrafficEvent(
        traffic_event_id="te1",
        location="Shirdi",
        severity="HIGH",
        description="Heavy traffic",
        active=True
    )
    db.add(te)
    db.commit()
    db.close()
    
    payload = {
        "source": "Kopargaon",
        "destination": "Rahata",
        "date": "2026-09-01",
        "weight_kg": 50
    }
    response = client.post("/api/logistics/search", json=payload)
    data = response.json()
    rec = data["recommendations"][0]
    assert rec["score"] < 100
    assert any("Traffic warning at Shirdi" in reason for reason in rec["reasons"])

def test_8_no_passenger_load_data():
    # TEST 8: No passenger-load data exists.
    payload = {
        "source": "Kopargaon",
        "destination": "Rahata",
        "date": "2026-09-01",
        "weight_kg": 50
    }
    response = client.post("/api/logistics/search", json=payload)
    data = response.json()
    rec = data["recommendations"][0]
    # Verify no fabricated passenger load in reasons
    assert not any("passenger load" in reason.lower() for reason in rec["reasons"])

def test_9_no_route_exists():
    # TEST 9: No route exists.
    payload = {
        "source": "Pune",
        "destination": "Mumbai",
        "date": "2026-09-01",
        "weight_kg": 50
    }
    response = client.post("/api/logistics/search", json=payload)
    data = response.json()
    assert data["status"] == "NO_MATCH"
    assert "No active route found" in data["reason"]

def test_10_multiple_eligible_buses_ranked():
    # TEST 10: Multiple eligible buses. Results ranked deterministically.
    db = TestingSessionLocal()
    # Add a second bus and schedule that perfectly matches time
    bus3 = domain.Bus(
        bus_id="bus_3",
        bus_number="MH-DEMO-3",
        service_type="EXPRESS",
        status="ACTIVE",
        parcel_enabled=True,
        data_source=domain.DataSource.DEMO
    )
    db.add(bus3)
    
    sch3 = domain.Schedule(
        schedule_id="sch_3",
        bus_id="bus_3",
        route_id="rt_1",
        service_date="2026-09-01",
        departure_time="10:00", # Better time match
        arrival_time="11:00",
        active=True,
        data_source=domain.DataSource.DEMO
    )
    db.add(sch3)
    
    # Give it capacity
    cap3_1 = domain.ParcelCapacity(
        capacity_id="cap3_1",
        bus_id="bus_3",
        schedule_id="sch_3",
        segment_id="seg1",
        max_safe_parcel_capacity_kg=100.0,
        reserved_capacity_kg=0.0
    )
    cap3_2 = domain.ParcelCapacity(
        capacity_id="cap3_2",
        bus_id="bus_3",
        schedule_id="sch_3",
        segment_id="seg2",
        max_safe_parcel_capacity_kg=100.0,
        reserved_capacity_kg=0.0
    )
    db.add_all([cap3_1, cap3_2])
    db.commit()
    db.close()
    
    payload = {
        "source": "Kopargaon",
        "destination": "Rahata",
        "date": "2026-09-01",
        "time": "10:00",
        "weight_kg": 50
    }
    response = client.post("/api/logistics/search", json=payload)
    data = response.json()
    recs = data["recommendations"]
    assert len(recs) == 2
    # Bus 3 should be rank 1 because time exactly matches, Bus 1 should be rank 2
    assert recs[0]["bus_id"] == "bus_3"
    assert recs[0]["score"] >= recs[1]["score"]
