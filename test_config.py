import os
from pydantic import ValidationError

def test_config():
    # 1. Default (development)
    os.environ["ENVIRONMENT"] = "development"
    if "DATABASE_URL" in os.environ:
        del os.environ["DATABASE_URL"]
        
    from app.core.config import Settings
    s = Settings()
    assert s.DATABASE_URL == "sqlite:///./koparman.db"
    print("Dev default OK")

    # 2. Production missing URL
    os.environ["ENVIRONMENT"] = "production"
    try:
        s = Settings()
        assert False, "Should have raised ValidationError"
    except ValidationError as e:
        assert "DATABASE_URL is required in production" in str(e)
        print("Prod missing URL OK")

    # 3. Production sqlite
    os.environ["DATABASE_URL"] = "sqlite:///./prod.db"
    try:
        s = Settings()
        assert False, "Should have raised ValidationError"
    except ValidationError as e:
        assert "Cannot use SQLite in production" in str(e)
        print("Prod sqlite OK")

    # 4. Production postgres:// (Render fix)
    os.environ["DATABASE_URL"] = "postgres://user:pass@host/db"
    s = Settings()
    assert s.DATABASE_URL == "postgresql://user:pass@host/db"
    print("Prod postgres->postgresql fix OK")

if __name__ == "__main__":
    test_config()
