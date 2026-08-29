from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Kopar-Man Backend"
    API_V1_STR: str = "/api"
    
    # DATABASE
    DATABASE_URL: str = "sqlite:///./koparman.db"  # Default to sqlite for easy hackathon setup if Postgres isn't provided, but expect PG
    # eTravos Integration
    ETRAVOS_ENABLED: bool = False
    ETRAVOS_BASE_URL: str = "https://api.etravos.com/v1"
    ETRAVOS_CONSUMER_KEY: Optional[str] = None
    ETRAVOS_CONSUMER_SECRET: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
