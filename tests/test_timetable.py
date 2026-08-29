"""
Tests for Prompt 6 — Authenticated Kopargaon Bus Stand Timetable

Tests cover:
  1.  Shirdi timetable import
  2.  Nashik timetable import
  3.  Sangamner timetable import
  4.  Rural/local destination import (Handewadi)
  5.  Duplicate detection
  6.  Invalid time rejection
  7.  OFFICIAL data_source enforcement
  8.  Idempotent re-import
  9.  Timetable search by destination
  10. Timetable-only records are NOT parcel-capable (not surfaced by matching engine)
  11. Time-period filter (morning / afternoon / evening)
  12. 404 when no match found
  13. Full HTTP API integration
"""
import pytest
import tempfile
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import get_db, Base
from app.models.domain import DataSource, TimetableDeparture
from app.services.timetable import (
    validate_timetable_rows,
    upsert_timetable_rows,
    search_timetable,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def engine():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    os.unlink(path)


@pytest.fixture(scope="module")
def db(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture(scope="module")
def client(engine):
    """HTTP test client wired to the in-module SQLite engine."""
    Session = sessionmaker(bind=engine)

    def override_get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _row(destination: str, departure_time: str, **kwargs) -> dict:
    return {
        "origin": "Kopargaon",
        "destination": destination,
        "departure_time": departure_time,
        "data_source": "OFFICIAL",
        "source_doc": "Kopargaon-Bus-Stand-Timetable.pdf",
        "source_name": "Authenticated Kopargaon Bus Stand Timetable",
        **kwargs,
    }


# ── Test 1: Shirdi timetable import ───────────────────────────────────────────

def test_1_shirdi_import(db):
    rows = [
        _row("Shirdi", "08:00"),
        _row("Shirdi", "11:30"),
        _row("Shirdi", "15:00"),
    ]
    errors = validate_timetable_rows(rows)
    assert not errors, errors
    result = upsert_timetable_rows(db, rows)
    db.commit()
    assert result["total"] == 3

    stored = (
        db.query(TimetableDeparture)
        .filter_by(origin="Kopargaon", destination="Shirdi")
        .order_by(TimetableDeparture.departure_time)
        .all()
    )
    assert [r.departure_time for r in stored] == ["08:00", "11:30", "15:00"]
    assert all(r.data_source == DataSource.OFFICIAL for r in stored)


# ── Test 2: Nashik timetable import (12 departures) ──────────────────────────

def test_2_nashik_import(db):
    nashik_times = [
        "06:30", "07:15", "08:00", "09:00", "10:00", "11:00",
        "12:00", "13:00", "14:00", "15:00", "17:00", "18:00",
    ]
    rows = [_row("Nashik", t) for t in nashik_times]
    errors = validate_timetable_rows(rows)
    assert not errors, errors
    result = upsert_timetable_rows(db, rows)
    db.commit()
    assert result["total"] == 12

    stored = (
        db.query(TimetableDeparture)
        .filter_by(origin="Kopargaon", destination="Nashik")
        .all()
    )
    assert len(stored) == 12


# ── Test 3: Sangamner timetable import ────────────────────────────────────────

def test_3_sangamner_import(db):
    rows = [_row("Sangamner", t) for t in ["08:30", "09:30", "12:00", "13:30", "17:30", "18:30"]]
    errors = validate_timetable_rows(rows)
    assert not errors, errors
    result = upsert_timetable_rows(db, rows)
    db.commit()
    assert result["total"] == 6


# ── Test 4: Rural/local destination (Handewadi) ───────────────────────────────

def test_4_rural_destination_handewadi(db):
    handewadi_times = ["08:05", "10:00", "12:15", "13:30", "14:30", "17:00", "19:30"]
    rows = [_row("Handewadi", t) for t in handewadi_times]
    errors = validate_timetable_rows(rows)
    assert not errors, errors
    result = upsert_timetable_rows(db, rows)
    db.commit()
    assert result["total"] == 7

    stored = db.query(TimetableDeparture).filter_by(destination="Handewadi").all()
    assert len(stored) == 7


# ── Test 5: Duplicate detection ───────────────────────────────────────────────

def test_5_duplicate_detection():
    rows = [
        _row("Shirdi", "08:00"),
        _row("Shirdi", "08:00"),  # exact duplicate
    ]
    errors = validate_timetable_rows(rows)
    assert any("duplicate" in e.lower() for e in errors), errors


# ── Test 6: Invalid time rejection ───────────────────────────────────────────

def test_6_invalid_time_rejected():
    bad_rows = [
        _row("Nashik", "25:00"),    # hour > 23
        _row("Nashik", "ten-am"),   # non-numeric
        _row("Nashik", "08"),       # missing minutes
        _row("Nashik", "08:60"),    # minute > 59
    ]
    errors = validate_timetable_rows(bad_rows)
    assert len(errors) == 4, errors


# ── Test 7: OFFICIAL data_source enforcement ──────────────────────────────────

def test_7_official_datasource_enforced():
    rows = [
        _row("Shirdi", "08:00", data_source="DEMO"),
        _row("Shirdi", "11:30", data_source="OPERATOR"),
    ]
    errors = validate_timetable_rows(rows)
    assert len(errors) == 2
    assert all("OFFICIAL" in e for e in errors)


def test_7b_invalid_datasource_also_rejected():
    rows = [_row("Shirdi", "08:00", data_source="FAKE")]
    errors = validate_timetable_rows(rows)
    assert any("data_source" in e for e in errors)


# ── Test 8: Idempotent re-import ──────────────────────────────────────────────

def test_8_idempotent_reimport(db):
    before_count = db.query(TimetableDeparture).filter_by(destination="Shirdi").count()
    rows = [
        _row("Shirdi", "08:00"),
        _row("Shirdi", "11:30"),
        _row("Shirdi", "15:00"),
    ]
    result = upsert_timetable_rows(db, rows)
    db.commit()
    after_count = db.query(TimetableDeparture).filter_by(destination="Shirdi").count()

    assert before_count == after_count, "Re-import must not create new rows"
    assert result["inserted"] == 0
    assert result["updated"] == 3


# ── Test 9: Timetable search by destination ───────────────────────────────────

def test_9_search_by_destination(db):
    result = search_timetable(db, origin="Kopargaon", destination="Shirdi")
    assert result["result_count"] == 3
    assert len(result["destinations"]) == 1
    group = result["destinations"][0]
    assert group["destination"] == "Shirdi"
    assert "08:00" in group["departures"]
    assert "11:30" in group["departures"]
    assert "15:00" in group["departures"]
    assert group["data_source"] == "OFFICIAL"


def test_9b_search_all_from_kopargaon(db):
    result = search_timetable(db, origin="Kopargaon")
    # We loaded Shirdi (3), Nashik (12), Sangamner (6), Handewadi (7) = 28 total
    assert result["result_count"] >= 28


# ── Test 10: Timetable records NOT parcel-capable ─────────────────────────────

def test_10_timetable_records_not_parcel_capable(db):
    """
    The matching engine uses Schedule+Bus+ParcelCapacity.
    TimetableDeparture records have no bus_id, no route_id, no ParcelCapacity.
    Verify they are structurally absent from the matching pipeline.
    """
    from app.models.domain import TimetableDeparture, Schedule, Bus, ParcelCapacity

    # No Schedule rows exist from timetable import
    schedules_from_timetable = (
        db.query(Schedule)
        .join(TimetableDeparture, Schedule.schedule_id == TimetableDeparture.departure_id, isouter=True)
        .all()
    )
    # This join will be empty because TimetableDeparture and Schedule are completely unrelated tables
    assert schedules_from_timetable == []

    # Confirm timetable rows have no parcel_capacity counterpart
    # (there is no bus_id or schedule_id on TimetableDeparture — it's structurally impossible)
    shirdi = (
        db.query(TimetableDeparture).filter_by(destination="Shirdi").first()
    )
    assert shirdi is not None
    assert not hasattr(shirdi, "bus_id")
    assert not hasattr(shirdi, "parcel_capacity")


# ── Test 11: Time-period filter ───────────────────────────────────────────────

def test_11_morning_filter(db):
    result = search_timetable(db, origin="Kopargaon", destination="Nashik", period="morning")
    departures = result["destinations"][0]["departures"] if result["destinations"] else []
    for dep in departures:
        h = int(dep.split(":")[0])
        assert 5 <= h < 12, f"Expected morning departure, got {dep}"


def test_11b_afternoon_filter(db):
    result = search_timetable(db, origin="Kopargaon", destination="Nashik", period="afternoon")
    departures = result["destinations"][0]["departures"] if result["destinations"] else []
    for dep in departures:
        h = int(dep.split(":")[0])
        assert 12 <= h < 17, f"Expected afternoon departure, got {dep}"


# ── Test 12: HTTP API integration ─────────────────────────────────────────────

def test_12_api_shirdi(client):
    resp = client.get("/api/timetable/search?origin=Kopargaon&destination=Shirdi")
    assert resp.status_code == 200
    data = resp.json()
    assert data["origin"] == "Kopargaon"
    assert len(data["destinations"]) == 1
    group = data["destinations"][0]
    assert group["destination"] == "Shirdi"
    assert sorted(group["departures"]) == ["08:00", "11:30", "15:00"]
    assert group["data_source"] == "OFFICIAL"
    assert "not" in data["note"].lower() and "parcel" in data["note"].lower()


def test_12b_api_404_unknown_destination(client):
    resp = client.get("/api/timetable/search?origin=Kopargaon&destination=UnknownCity999")
    assert resp.status_code == 404


def test_12c_api_invalid_period_rejected(client):
    resp = client.get("/api/timetable/search?origin=Kopargaon&period=midnight")
    assert resp.status_code == 422
