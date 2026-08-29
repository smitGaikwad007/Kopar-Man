from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "Kopar-Man Backend"
    API_V1_STR: str = "/api"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # DATABASE
    DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")
    
    @field_validator("DATABASE_URL", mode="before")
    def validate_db_url(cls, v: Optional[str]) -> str:
        env = os.getenv("ENVIRONMENT", "development")
        if env == "production":
            if not v:
                raise ValueError("DATABASE_URL is required in production environment.")
            if v.startswith("sqlite"):
                raise ValueError("Cannot use SQLite in production environment.")
            # SQLAlchemy 1.4+ requires postgresql:// instead of postgres://
            if v.startswith("postgres://"):
                v = v.replace("postgres://", "postgresql://", 1)
            return v
        else:
            return v or "sqlite:///./koparman.db"

    # eTravos Integration
    ETRAVOS_ENABLED: bool = False
    ETRAVOS_BASE_URL: str = "https://api.etravos.com/v1"
    ETRAVOS_CONSUMER_KEY: Optional[str] = None
    ETRAVOS_CONSUMER_SECRET: Optional[str] = None
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore"
    }

settings = Settings()
