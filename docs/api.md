# API Documentation

The REST API is designed to return structured JSON data.

## Core Endpoints

### Transport Network
- `GET /api/routes/search`: Search routes (filters: origin, destination, active).
- `GET /api/buses/search`: Search buses (filters: bus_number, parcel_enabled, status).
- `GET /api/schedules/search`: Find schedules (filters: route_id, date, time, active).

### Logistics
- `POST /api/logistics/search`: Deterministic logistics matching engine. Returns matching transport services or `NO_MATCH` with detailed reasons. Does not reserve capacity.
- `POST /api/parcels`: Create a new parcel shipment.
- `GET /api/parcels/{parcel_id}`: Get parcel details.
- `GET /api/parcels/{parcel_id}/tracking`: Get parcel event history.
- `POST /api/parcels/{parcel_id}/events`: Add a tracking event.

Refer to the Swagger UI (`/docs`) when running locally for complete schema definitions.

---

## Parcel Booking — POST /api/logistics/book

Books a parcel shipment with atomic capacity reservation.

**Request body:**
```json
{
  "schedule_id": "sch_1",
  "route_id": "rt_1",
  "source": "Kopargaon",
  "destination": "Rahata",
  "weight_kg": 50,
  "sender_name": "Ramesh Patil",
  "sender_phone": "9876540001",
  "receiver_name": "Suresh Jadhav",
  "receiver_phone": "9876540002",
  "parcel_type": "FARM_PRODUCE"
}
```

**Success response:**
```json
{
  "status": "BOOKED",
  "tracking_id": "KPM-3F7A1B2C",
  "parcel_id": "...",
  "schedule_id": "sch_1",
  "bus_number": "MH-DEMO-1",
  "source": "Kopargaon",
  "destination": "Rahata",
  "weight_kg": 50,
  "departure_time": "10:00",
  "arrival_time": "11:30",
  "capacity_reserved": { "segment_count": 2, "weight_kg": 50 }
}
```

**Error codes:**
- `404` schedule not found
- `400` schedule inactive, bus unavailable, bus not parcel-enabled, route mismatch, invalid stop order, insufficient capacity

---

## Cancel Parcel — POST /api/parcels/{parcel_id}/cancel

```json
{ "reason": "Customer request" }
```
Allowed from: CREATED, RESERVED, CONFIRMED, RECEIVED. Releases capacity automatically.

---

## Track by tracking_id — GET /api/parcels/track/{tracking_id}

WhatsApp-friendly lookup. Returns full parcel + event history.
Verification codes are NOT included in this response.

---

## Parcel State Machine

```
CREATED → RESERVED → CONFIRMED → RECEIVED → LOADED → IN_TRANSIT → ARRIVED → DELIVERED
   ↓           ↓          ↓          ↓
CANCELLED  CANCELLED  CANCELLED  CANCELLED
```

Use `POST /api/parcels/{parcel_id}/events` with `{"event_type": "<STATE>", "created_by": "..."}` to advance the state.
