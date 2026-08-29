import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import get_db, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import tempfile
import os

@pytest.fixture(scope="module")
def client():
    # Use in-memory SQLite for testing
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(bind=engine)

    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()

def test_sync_transport_data_disabled_etravos(client):
    # Should succeed but return 0 counts because ETRAVOS_ENABLED = False by default
    response = client.post("/api/admin/transport/sync", json={"provider": "etravos"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["counts"]["buses"] == 0
    assert data["counts"]["routes"] == 0

def test_sync_transport_data_invalid_provider(client):
    response = client.post("/api/admin/transport/sync", json={"provider": "unknown"})
    assert response.status_code == 400
    assert "not supported" in response.json()["detail"]
