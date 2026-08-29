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
