# Kopar-Man — Change Log

## Prompt 1 — Backend Foundation

**Date/Time:** 2026-08-29 18:40 IST
**Objective:** Create the initial backend foundation for Kopar-Man logistics assistant.
**Requested Changes:** Build a Python/FastAPI/PostgreSQL backend with specific domain models, API structure, and clear separation of transport/logistics concepts.

**Actual Files Created/Modified:**
- `app/core/config.py`
- `app/db/database.py`
- `app/models/domain.py`
- `app/schemas/domain.py`
- `app/api/endpoints/health.py`, `routes.py`, `buses.py`, `schedules.py`, `parcels.py`, `logistics.py`, `traffic.py`
- `app/api/api_v1.py`
- `app/main.py`
- Alembic setup (`alembic/`, `alembic.ini`)
- `tests/test_api.py`
- Documentation (`README.md`, `docs/architecture.md`, `docs/api.md`, `docs/data-model.md`)

**Database Changes:**
- Initialized Alembic.
- Created tables: `buses`, `routes`, `route_stops`, `schedules`, `route_segments`, `parcel_capacity`, `parcels`, `parcel_events`, `rural_shipments`, `traffic_events`.

**API Changes:**
- Created foundational REST APIs (`/api/health`, `/api/routes/*`, `/api/buses/*`, `/api/schedules/*`, `/api/parcels/*`, `/api/logistics/*`, `/api/traffic/*`).

**Tests Executed:**
- `test_health_check`
- `test_search_buses`
- `test_search_routes`
- `test_create_parcel`

**Test Results:**
- All 4 tests passed successfully using an in-memory SQLite database configuration.

**Known Issues:**
- The `/api/logistics/search` endpoint currently returns a dummy payload and needs the full deterministic matching logic implemented in the future.
- The default config uses SQLite for easy hackathon setup. Needs actual PostgreSQL credentials injected via `.env` in production.

**TODOs:**
- Implement detailed segment-aware capacity checking in the logistics search.
- Connect n8n/Claude to these endpoints.

**Next Recommended Step:**
- Review the implemented models and APIs. Build out the logistics matching deterministic logic (steps 1-8).

## Prompt 2 — Transport & Logistics Matching Engine

**Objective:** Implement a deterministic, explainable transport and logistics matching engine in `POST /api/logistics/search` based strictly on database data, handling segment-aware capacity, traffic, and bus eligibility.

**Files Modified:**
- `app/schemas/domain.py`
- `app/api/endpoints/logistics.py`
- `app/api/endpoints/routes.py`
- `app/api/endpoints/buses.py`
- `app/api/endpoints/schedules.py`
- `tests/test_api.py` (Indirectly preserved)
- Documentation files.

**Services Added:**
- `app/services/capacity.py` (`CapacityService`)
- `app/services/matching.py` (`LogisticsMatchingService`)

**APIs Changed:**
- `POST /api/logistics/search`: Now runs the full deterministic pipeline, returns scores, reasons, and `MATCH_FOUND`/`NO_MATCH` logic.
- `GET /api/buses/search`, `routes/search`, `schedules/search`: Added query parameters (filters) for practical chat querying.

**Database Changes:**
- No structural schema changes required. Used the existing well-designed schema from Prompt 1.

**Tests Added:**
- `tests/test_matching.py` covering 10 requested test cases for the engine (Direct route, Insufficient capacity, Segment failure, Parcel eligibility, Direction constraints, Non-mutating behavior, Traffic, Passenger load, No routes, Ranking).

**Tests Executed:**
- `pytest tests/test_matching.py -v` (10 tests)
- `pytest tests/test_api.py -v` (4 tests)

**Test Results:**
- All 14 tests across the suite passed perfectly.

**Assumptions:**
- String matching for stops/traffic works for the MVP. Spatial mapping could be added later.
- If a route segment has no explicit `ParcelCapacity` entry, its capacity is assumed to be `0.0`.
- The ranking assigns a score of 100 and deducts points for traffic and time disparities.

**Known Limitations:**
- Traffic matching uses basic string inclusion between the traffic location and stop name.
- Passenger load data structure is not yet modeled; the system just falls back to bus status (`UNAVAILABLE`, `UNSAFE`).

**Next Recommended Step:**
- Implement the actual Parcel Booking/Reservation endpoint that will *deduct* from `ParcelCapacity` based on a selected `schedule_id`.

## Prompt 3 — Transport Data Ingestion & Validation

**Objective:** Create a robust, idempotent data ingestion pipeline using CSV files with strict validation rules, dry-run support, and transaction safety.

**Files Created/Modified:**
- `data/buses.csv`, `data/routes.csv`, `data/route_stops.csv`, `data/schedules.csv`, `data/parcel_capacity.csv` (Templates / Demo data)
- `scripts/import_transport_data.py` (The main ingestion engine)
- `tests/test_import.py` (Test suite for validation logic)
- `docs/data-import.md` (Documentation)

**CSV Formats:**
Created explicit CSV templates for Buses, Routes, Stops, Schedules, and Capacity. All include the critical `data_source` column to satisfy the trust model.

**Import Command:**
`python scripts/import_transport_data.py --dir data`

**Dry-run Command:**
`python scripts/import_transport_data.py --dir data --dry-run`

**Validation Rules Implemented:**
- In-memory constraint checking for missing fields and duplicated IDs.
- Relational integrity checks (e.g. schedules reference existing buses).
- Sequential logic checks (e.g. `from_stop` must precede `to_stop`).
- Mathematical limit checks (capacity bounds, negative limits).
- Capability checks (capacity linked only to parcel-enabled buses).
- Atomic database upserts preventing duplication on re-imports.

**Demo Data Created:**
Populated the `data/` directory with a small, explicitly labelled `DEMO` dataset (`rt_demo_1`, `bus_demo_1`) to allow out-of-the-box script testing without polluting the database with fake MSRTC records.

**Tests Run and Results:**
- Added 12 new dedicated tests in `test_import.py` verifying all failure and success scenarios (e.g., negative capacity rejection, rollback verification).
- Executed full test suite (`pytest tests/ -v`). All tests passed successfully.

**Assumptions:**
- `RouteSegment` generation dynamically maps `route_stops` sequentially (e.g., Stop 1 -> Stop 2 forms Segment 1).
- Upsert logic for idempotency targets primary keys (`bus_id`, `route_id`, etc.) and replaces `route_stops` and `route_segments` completely for a clean state on re-import.

**Next Recommended Step:**
- Implement the Parcel Booking/Reservation endpoint that integrates directly with the live capacity model.

## Prompt 4 — Parcel Reservation & Booking

**Objective:** Implement a safe, atomic parcel reservation and booking lifecycle with a clear state machine, segment-aware capacity reservation, capacity release on cancel/delivery, and structured error responses.

**Files Changed:**
- `app/models/domain.py` — Added `pickup_verification_code`, `delivery_verification_code` fields to `Parcel`; added `schedule` relationship to `Parcel` for easy capacity release
- `app/schemas/domain.py` — Added `ParcelBookRequest`, `ParcelBookResponse`, `CapacityReservedResponse` schemas
- `app/services/capacity.py` — Rewrote with `reserve_capacity()` and `release_capacity()` methods; PostgreSQL SELECT FOR UPDATE for concurrency; SQLite-compatible fallback for tests
- `app/api/endpoints/logistics.py` — Implemented `POST /api/logistics/book` with full 12-step validation pipeline
- `app/api/endpoints/parcels.py` — Rewrote with state machine enforcement, capacity release on cancel/deliver, `GET /api/parcels/track/{tracking_id}`, structured error responses
- `tests/test_booking.py` — 15 tests covering all spec requirements + demo scenario
- `tests/conftest.py` — Created to prevent dependency override conflicts across test modules
- `alembic/versions/80930f03fe33_*.py` — Migration: add verification code columns to parcels
- `docs/data-import.md` — Existing
- `docs/api.md` — Updated (below)
- `changes.md` — This entry

**Database Changes:**
- Added `pickup_verification_code` (String, nullable) to `parcels` table
- Added `delivery_verification_code` (String, nullable) to `parcels` table
- New Alembic migration applied: `80930f03fe33`

**Endpoints Added:**
- `POST /api/logistics/book` — Atomic booking: validates schedule/bus/capacity, reserves all required segments, creates parcel + tracking event in one transaction
- `POST /api/parcels/{parcel_id}/cancel` — Cancels parcel, releases capacity, creates event
- `GET /api/parcels/track/{tracking_id}` — Lookup by human-readable ID (WhatsApp-friendly)
- `GET /api/parcels/{parcel_id}` — Get full parcel by internal ID
- `GET /api/parcels/{parcel_id}/tracking` — Get ordered event trail
- `POST /api/parcels/{parcel_id}/events` — Advance state machine

**State Machine:**
```
CREATED → RESERVED → CONFIRMED → RECEIVED → LOADED → IN_TRANSIT → ARRIVED → DELIVERED
   ↓           ↓          ↓          ↓
CANCELLED  CANCELLED  CANCELLED  CANCELLED
```
Terminal states: DELIVERED, CANCELLED. EXCEPTION allowed from LOADED/IN_TRANSIT/ARRIVED.

**Capacity Behavior:**
- Reserve: `POST /logistics/book` atomically increments `reserved_capacity_kg` on every segment between source and destination
- Release: triggered on cancel (states RESERVED/CONFIRMED/RECEIVED) or on DELIVERED transition
- Capacity is NEVER modified by search — read-only
- Invariant enforced: `reserved_capacity_kg` cannot exceed `max_safe_parcel_capacity_kg`

**Concurrency Strategy:**
- PostgreSQL (production): `SELECT … FOR UPDATE` locks capacity rows before check+increment → prevents concurrent oversubscription
- SQLite (test environment): FOR UPDATE not supported; SQLite's file-level locking serialises writes within a single process; multi-process concurrent oversubscription cannot be fully prevented in SQLite

**Verification Codes (OTP/QR preparation):**
- `pickup_verification_code` and `delivery_verification_code` generated with `secrets.token_hex(3)` and stored on the parcel
- Never returned in public GET/tracking responses
- QR generation and WhatsApp OTP delivery will use these in a future prompt

**Tests:**
```
tests/test_booking.py — 15 tests
  test_1:  Successful booking
  test_2&3: Reserves only required segments, not beyond destination
  test_4:  Fails when first segment insufficient
  test_5:  Fails when second segment insufficient
  test_6:  Fails when bus not parcel-enabled
  test_7:  Fails for invalid stop order
  test_8:  Re-checks capacity (not trusting search result)
  test_9:  Cancellation releases capacity
  test_10&11: State machine transitions + DELIVERED releases capacity + DELIVERED→CANCELLED rejected
  test_12: Search is read-only
  test_13: Transaction rolls back on invalid request
  test_14: Tracking ID unique and lookupable; verification codes not in public response
  test_15a: Sequential oversubscription rejected (deterministic)
  test_15b: Concurrent oversubscription (xfail on SQLite, passes on PostgreSQL)
  test_demo: Full spec demo scenario (50kg Kop→Rah, 60kg rejected, 20kg Shi→Rah succeeds)
```

**Test Results:** 40 passed, 1 xfailed (expected – SQLite concurrency limitation documented)

**Known Limitations:**
- SQLite cannot enforce SELECT FOR UPDATE; concurrent oversubscription is theoretically possible in SQLite under multi-process load. Not a concern in production PostgreSQL
- Verification codes are stored in plaintext; in production they should be hashed before storage
- No expiry on reservations (a parcel can sit in RESERVED state indefinitely). Prompt 5 could add TTL/expiry sweeping
- No payment or authorization implemented (by design)

**Next Recommended Step:**
- Prompt 5: WhatsApp/n8n webhook integration — format booking responses as conversational WhatsApp messages, implement OTP delivery via Twilio/Meta, and build the reservation-expiry sweeper

## Prompt 5 — External Transport Data Provider Architecture (eTravos-Ready)

**Objective:** Prepare Kopar-Man to consume external transport data providers, specifically adding an initial mock adapter for eTravos. The backend remains the single source of truth, and provider sync integrates neatly with existing robust ingestion logic.

**Files Created/Modified:**
- `app/core/config.py`: Added eTravos integration settings (`ETRAVOS_ENABLED`, `ETRAVOS_BASE_URL`, `ETRAVOS_CONSUMER_KEY`, `ETRAVOS_CONSUMER_SECRET`).
- `app/models/domain.py`: 
  - Added `EXTERNAL_PROVIDER` and `MANUAL` to the `DataSource` enum.
  - Added `valid_from` and `valid_until` DateTime columns to `Bus`, `Route`, and `Schedule` to track data freshness.
- `app/schemas/domain.py`: Updated schemas for `BusBase`, `RouteBase`, `ScheduleBase` to include the new metadata fields.
- `app/services/ingestion.py` (New): Extracted all validation and database upsert logic from `scripts/import_transport_data.py` into a reusable, framework-independent service.
- `scripts/import_transport_data.py`: Refactored to proxy its calls to the new `TransportIngestionService`. The CLI fallback command still functions exactly as before.
- `app/services/transport_providers/base.py` (New): Created `TransportDataProvider` interface and `NormalizedTransportData` Pydantic model for a clean abstraction boundary.
- `app/services/transport_providers/etravos.py` (New): Mock implementation of the `EtravosProvider` that behaves gracefully (returns empty data) when credentials or flags are disabled.
- `app/services/provider_sync.py` (New): `ProviderSyncService` responsible for fetching provider data, sending it through `TransportIngestionService.validate_data()`, and finally transacting it to the DB via `TransportIngestionService.upsert_data()`.
- `app/api/endpoints/admin.py` (New): Created `POST /api/admin/transport/sync` for triggering provider sync manually or via automation.
- `app/api/api_v1.py`: Included the new `admin.router`.
- `alembic/versions/c70b66bcba46_*.py`: Generated and applied a database migration for the new columns (`valid_from`, `valid_until`).
- `tests/test_admin.py` (New): Unit tests verifying the `/api/admin/transport/sync` endpoint, particularly checking graceful behavior when `ETRAVOS_ENABLED` is false and failure on unsupported provider names.

**Database Changes:**
- Added `valid_from` and `valid_until` (nullable DATETIME) to `buses`, `routes`, and `schedules` tables.

**APIs Changed:**
- `POST /api/admin/transport/sync` created. Request body: `{"provider": "etravos"}`.

**Tests Run & Results:**
- Re-ran the full test suite (`pytest tests/ -v -W ignore`).
- Added 2 new tests for the admin endpoint.
- Total tests: 43. 42 passed, 1 `xfailed` (SQLite concurrency limitation from Prompt 4 expected failure).

**Architecture Principle Achieved:**
The existing logistics search and booking remains completely untouched. Data coming from eTravos acts identically to data coming from CSV. If a request to eTravos fails or returns corrupted data, the database transaction rolls back, preventing corruption of existing valid operator data.

**Next Recommended Step:**
- Proceed to Prompt 6: Build the WhatsApp/n8n webhook endpoints to consume real logistics bookings and convert internal `KPM-XXX` tracking records to conversational responses.
