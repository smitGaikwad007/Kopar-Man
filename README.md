# Kopar-Man Backend

Backend API for Kopar-Man, a WhatsApp-based intelligent transportation and rural logistics assistant for Kopargaon, Maharashtra.

## Overview
This backend acts as the single source of truth for transport routes, schedules, parcel capacity, and shipment tracking. It features a deterministic logistics matching engine that respects segment-aware cargo capacity constraints without inventing data.

## Getting Started

1. **Virtual Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Database Setup**:
   The default configuration uses SQLite for local fast iteration. For production, set `DATABASE_URL` in your `.env` file to your PostgreSQL instance.
   ```bash
   alembic upgrade head
   ```

4. **Run Server**:
   ```bash
   uvicorn app.main:app --reload
   ```

5. **API Documentation**:
   Navigate to `http://localhost:8000/docs` to see the interactive Swagger UI.

## Testing
Run tests using:
```bash
PYTHONPATH=. pytest tests/ -v
```
