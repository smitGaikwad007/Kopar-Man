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

# Use an in-memory SQLite database for testing

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
    yield

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "Kopar-Man Backend"}

def test_search_buses():
    # Insert demo bus
    db = TestingSessionLocal()
    bus = domain.Bus(bus_number="MH17-1234", service_type="EXPRESS", operator="MSRTC", status="ACTIVE", parcel_enabled=True)
    db.add(bus)
    db.commit()
    db.close()

    response = client.get("/api/buses/search?bus_number=MH17")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["bus_number"] == "MH17-1234"

def test_search_routes():
    # Insert demo route
    db = TestingSessionLocal()
    route = domain.Route(route_name="Kopargaon-Shirdi", origin="Kopargaon", destination="Shirdi")
    db.add(route)
    db.commit()
    db.close()

    response = client.get("/api/routes/search?origin=Kopar")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["origin"] == "Kopargaon"

def test_create_parcel():
    payload = {
        "sender_name": "Ramesh",
        "sender_phone": "9876543210",
        "receiver_name": "Suresh",
        "receiver_phone": "9876543211",
        "source_stop": "Kopargaon",
        "destination_stop": "Shirdi",
        "weight_kg": 15.5,
        "parcel_type": "AGRICULTURAL"
    }
    response = client.post("/api/parcels", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["sender_name"] == "Ramesh"
    assert data["status"] == "CREATED"
    assert "tracking_id" in data
    
    parcel_id = data["parcel_id"]
    
    # Check tracking events
    tracking_response = client.get(f"/api/parcels/{parcel_id}/tracking")
    assert tracking_response.status_code == 200
    tracking_data = tracking_response.json()
    assert len(tracking_data) == 1
    assert tracking_data[0]["event_type"] == "CREATED"
