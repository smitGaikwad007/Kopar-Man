# Transport Data Ingestion

The backend includes a robust validation and ingestion pipeline for importing verified transport data.

## Usage

1. **Prepare CSV files** in a directory (e.g., `data/`):
   - `buses.csv`
   - `routes.csv`
   - `route_stops.csv`
   - `schedules.csv`
   - `parcel_capacity.csv`
   
2. **Dry Run (Validation Only)**:
   It's highly recommended to validate your dataset before modifying the production database.
   ```bash
   python scripts/import_transport_data.py --dir data --dry-run
   ```
   
3. **Import**:
   ```bash
   python scripts/import_transport_data.py --dir data
   ```

## Validation Rules
The import script enforces strict validation before committing any data:
- **Foreign Keys**: Stops must reference valid routes, schedules must reference valid buses/routes, capacity must reference valid schedules/segments.
- **Stop Sequences**: Must increase monotonically.
- **Directional Capacity**: Capacity `from_stop` must occur before `to_stop` in the route sequence.
- **Numeric Limits**: Capacity cannot be negative, and reserved capacity cannot exceed max safe capacity.
- **Parcel Capability**: Capacity cannot be assigned to a non-parcel-enabled bus.
- **Idempotency**: Existing records (matched by primary keys like `bus_id`) are safely merged/updated rather than blindly duplicated.
- **Transaction Safety**: The entire import runs inside a single database transaction. If any error occurs, all changes are rolled back.

## Data Source Trust Model
Every record must have a `data_source` column indicating its origin. Allowed values:
- `OFFICIAL`: Verified data from MSRTC or official transport authorities.
- `OPERATOR`: Data provided directly by private transport operators.
- `VERIFIED_LOCAL`: Data crowdsourced and verified by local trusted agents.
- `SIMULATION`: Data explicitly generated for algorithmic testing.
- `DEMO`: Placeholder/dummy data for UI testing.

**Never** label simulated data as `OFFICIAL`.

## Timetable Import (Prompt 6)

Import the authenticated Kopargaon Bus Stand Timetable from `data/timetable.csv`:

```bash
# Dry-run (validate only)
PYTHONPATH=. python scripts/import_timetable.py --dry-run

# Import to default SQLite (local dev)
PYTHONPATH=. python scripts/import_timetable.py

# Import to PostgreSQL (Render production)
PYTHONPATH=. python scripts/import_timetable.py --db "$DATABASE_URL"
```

The CSV must contain columns: `origin, destination, departure_time, data_source, source_doc, source_name`

All rows must carry `data_source=OFFICIAL`. Re-imports are fully idempotent — no duplicates will be created.
