from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.api_v1 import api_router
from app.core.config import settings
from app.db.database import Base, engine

# Create tables for hackathon fast iteration (In production use Alembic)
import app.models.domain


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API for Kopar-Man logistics and transport assistant",
    version="0.1.0",
)

# Security: CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Update for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    return {"message": "Welcome to Kopar-Man API"}
