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

## Deployment on Render

Kopar-Man is designed to be easily deployed to [Render](https://render.com/).

### Method 1: Using render.yaml (Recommended)
1. Connect your GitHub repository to Render using the **Blueprint** feature.
2. Render will read `render.yaml` and automatically provision both a Web Service and a PostgreSQL database.
3. Migrations will run automatically during startup.

### Method 2: Manual Web Service Setup
1. Create a new **Web Service** on Render.
2. Create a new **PostgreSQL Database** on Render.
3. Configure the Web Service:
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Set Environment Variables on the Web Service:
   - `ENVIRONMENT`: `production`
   - `DATABASE_URL`: *(Paste the Internal Database URL from your Render PostgreSQL instance)*
   - `PYTHON_VERSION`: `3.13.7` (or your preferred compatible Python 3.x version)

**Note:** The application validates `DATABASE_URL` during startup. If `ENVIRONMENT=production` is set, the application will crash if the database URL points to `sqlite` or is completely missing, ensuring the application never silently falls back to an ephemeral database in production.
