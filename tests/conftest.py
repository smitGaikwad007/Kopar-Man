"""
tests/conftest.py

Each test module uses its own SQLite file-based database to avoid engine
conflicts when running the full test suite (pytest tests/).

Each test file overrides app.dependency_overrides[get_db] with its own
engine; the conftest resets the override after the session.
"""
import pytest
from app.main import app
from app.db.database import get_db


@pytest.fixture(scope="session", autouse=True)
def reset_app_overrides():
    """Ensure dependency overrides are cleared between test modules."""
    yield
    app.dependency_overrides.clear()
