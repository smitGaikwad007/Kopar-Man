# Data Model

The domain model is designed to support both transport and logistics.

## Core Entities
1. **Bus**: Physical vehicle. Includes `parcel_enabled` flag.
2. **Route**: A transport path.
3. **RouteStop**: Ordered list of stops on a route.
4. **Schedule**: Specific trip times for a bus on a route.
5. **RouteSegment**: Sections between two consecutive stops (essential for segment-based capacity).
6. **ParcelCapacity**: Explicit, operator-approved cargo limits per segment.
7. **Parcel**: A shipment from a source stop to a destination stop.

## Segment-Aware Capacity
Capacity is tracked per segment. A parcel traveling from Stop A to Stop C over a route A->B->C consumes capacity on both A->B and B->C segments. 

The `CapacityService.check_segment_capacity()` queries `ParcelCapacity` across every `RouteSegment` dynamically based on `RouteStop.stop_sequence`.

---

## TimetableEntry (Prompt 6)

Represents a **single authenticated recurring departure** from an origin to a destination.

This model deliberately omits fields that are NOT present in the timetable source:

| Field | Present? | Reason for omission |
|---|---|---|
| `bus_id` | ❌ | Unknown — not provided by timetable |
| `arrival_time` | ❌ | Unknown — not provided by timetable |
| `service_date` | ❌ | Recurring timetable, not date-specific |
| Intermediate stops | ❌ | Not provided |
| `parcel_eligible` | Always `False` | Can only be established through explicit capacity data |

### Provenance Fields

| Field | Purpose |
|---|---|
| `data_source` | DataSource enum — always `OFFICIAL` for this timetable |
| `source_name` | Human-readable source label |
| `source_document` | Source file reference (e.g. PDF filename) |

### Separation from Parcel Logistics

`TimetableEntry` is stored in a **separate table** (`timetable_entries`) and is **never queried by the logistics matching engine**. Parcel transport requires explicit `Schedule` + `ParcelCapacity` records from the Prompt-3 pipeline.

## TimetableDeparture (Prompt 6)

Stores recurring authenticated timetable departures from Kopargaon Bus Stand.

**Why a separate model?**
The authenticated PDF source provides only origin, destination, and departure time. The existing `Schedule` model requires bus identity, route, service date, and arrival time — none of which are available. Creating fake values for missing fields would violate the backend's single-source-of-truth principle. `TimetableDeparture` stores exactly what is known.

**Key fields:** `departure_id`, `origin`, `destination`, `departure_time` (HH:MM), `data_source` (always OFFICIAL), `source_doc`, `source_name`, `valid_from`, `valid_until`.

**Parcel safety:** `TimetableDeparture` has no foreign key to `Bus`, `Route`, or `ParcelCapacity`. It is structurally excluded from the logistics matching engine. Only `Schedule` rows with verified parcel capacity appear in `/api/logistics/search`.
