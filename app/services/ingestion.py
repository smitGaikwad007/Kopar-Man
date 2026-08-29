from typing import Dict, Any, List, Optional
from collections import defaultdict
import uuid
from sqlalchemy.orm import Session
from app.models.domain import Bus, Route, RouteStop, Schedule, RouteSegment, ParcelCapacity, DataSource

def parse_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ('true', '1', 'yes', 't')
    return bool(val)

class TransportIngestionService:
    @staticmethod
    def validate_data(
        buses_data: List[Dict],
        routes_data: List[Dict],
        route_stops_data: List[Dict],
        schedules_data: List[Dict],
        parcel_cap_data: List[Dict]
    ) -> List[str]:
        """
        Validates the transport data arrays in-memory.
        Returns a list of error strings. Empty list means success.
        """
        errors = []
        
        buses = {}
        routes = {}
        schedules = {}
        route_stops = defaultdict(list)
        
        valid_sources = {s.value for s in DataSource}

        # Validate Buses
        for row in buses_data:
            bus_id = row.get('bus_id')
            if not bus_id:
                errors.append("Bus missing bus_id")
                continue
            if bus_id in buses:
                errors.append(f"Duplicate bus_id: {bus_id}")
            if row.get('data_source') not in valid_sources:
                errors.append(f"Invalid data_source for bus {bus_id}: {row.get('data_source')}")
            buses[bus_id] = row

        # Validate Routes
        for row in routes_data:
            route_id = row.get('route_id')
            if not route_id:
                errors.append("Route missing route_id")
                continue
            if route_id in routes:
                errors.append(f"Duplicate route_id: {route_id}")
            if row.get('data_source') not in valid_sources:
                errors.append(f"Invalid data_source for route {route_id}: {row.get('data_source')}")
            routes[route_id] = row

        # Validate Route Stops
        for row in route_stops_data:
            route_id = row.get('route_id')
            if route_id not in routes:
                errors.append(f"Route stop references unknown route_id: {route_id}")
                continue
            try:
                seq = int(row.get('stop_sequence'))
                route_stops[route_id].append((seq, row))
            except (ValueError, TypeError):
                errors.append(f"Invalid stop_sequence for route {route_id}")

        # Check route stops ordering
        for route_id, stops in route_stops.items():
            stops.sort(key=lambda x: x[0]) # sort by sequence
            seen_seq = set()
            prev_seq = 0
            for seq, row in stops:
                if seq in seen_seq:
                    errors.append(f"Duplicate stop_sequence {seq} in route {route_id}")
                if seq <= prev_seq:
                    errors.append(f"Stop sequence must increase strictly monotonically in route {route_id} (found {seq} after {prev_seq})")
                seen_seq.add(seq)
                prev_seq = seq

        # Validate Schedules
        for row in schedules_data:
            schedule_id = row.get('schedule_id')
            bus_id = row.get('bus_id')
            route_id = row.get('route_id')
            if schedule_id in schedules:
                errors.append(f"Duplicate schedule_id: {schedule_id}")
            if bus_id not in buses:
                errors.append(f"Schedule {schedule_id} references unknown bus_id: {bus_id}")
            if route_id not in routes:
                errors.append(f"Schedule {schedule_id} references unknown route_id: {route_id}")
            schedules[schedule_id] = row

        # Validate Parcel Capacity
        for row in parcel_cap_data:
            bus_id = row.get('bus_id')
            schedule_id = row.get('schedule_id')
            route_id = row.get('route_id')
            
            if bus_id not in buses:
                errors.append(f"Capacity references unknown bus_id: {bus_id}")
            elif not parse_bool(buses[bus_id].get('parcel_enabled', 'False')):
                errors.append(f"Capacity referenced non-parcel-enabled bus: {bus_id}")
                
            if schedule_id and schedule_id not in schedules:
                errors.append(f"Capacity references unknown schedule_id: {schedule_id}")
                
            if route_id not in routes:
                errors.append(f"Capacity references unknown route_id: {route_id}")
                continue
                
            try:
                max_cap = float(row.get('max_safe_capacity_kg', 0))
                res_cap = float(row.get('reserved_capacity_kg', 0))
                if max_cap < 0:
                    errors.append(f"Negative max capacity: {max_cap}")
                if res_cap < 0:
                    errors.append(f"Negative reserved capacity: {res_cap}")
                if res_cap > max_cap:
                    errors.append(f"Reserved capacity {res_cap} exceeds max {max_cap}")
            except (ValueError, TypeError):
                errors.append("Invalid capacity numerical values")
                
            # Verify stops exist and are ordered correctly
            from_stop = row.get('from_stop')
            to_stop = row.get('to_stop')
            stops = route_stops.get(route_id, [])
            from_seq = next((s[0] for s in stops if s[1]['stop_name'] == from_stop), -1)
            to_seq = next((s[0] for s in stops if s[1]['stop_name'] == to_stop), -1)
            
            if from_seq == -1:
                errors.append(f"from_stop {from_stop} not found in route {route_id}")
            if to_seq == -1:
                errors.append(f"to_stop {to_stop} not found in route {route_id}")
            if from_seq != -1 and to_seq != -1 and from_seq >= to_seq:
                errors.append(f"from_stop {from_stop} must occur before to_stop {to_stop} in route {route_id}")

        return errors

    @staticmethod
    def upsert_data(
        db: Session,
        buses_data: List[Dict],
        routes_data: List[Dict],
        route_stops_data: List[Dict],
        schedules_data: List[Dict],
        parcel_cap_data: List[Dict]
    ) -> Dict[str, Any]:
        """
        Upserts data into the database. Caller should handle commit/rollback.
        """
        source_counts = defaultdict(int)

        # 1. Upsert Buses
        for row in buses_data:
            bus_id = row['bus_id']
            db_bus = db.query(Bus).filter_by(bus_id=bus_id).first()
            if not db_bus:
                db_bus = Bus(bus_id=bus_id)
                db.add(db_bus)
            db_bus.bus_number = row['bus_number']
            db_bus.service_type = row.get('service_type')
            db_bus.operator = row.get('operator')
            db_bus.status = row.get('status')
            db_bus.parcel_enabled = parse_bool(row.get('parcel_enabled', 'False'))
            db_bus.data_source = row.get('data_source', 'DEMO')
            db_bus.valid_from = row.get('valid_from')
            db_bus.valid_until = row.get('valid_until')
            source_counts[db_bus.data_source] += 1

        # 2. Upsert Routes
        for row in routes_data:
            route_id = row['route_id']
            db_route = db.query(Route).filter_by(route_id=route_id).first()
            if not db_route:
                db_route = Route(route_id=route_id)
                db.add(db_route)
            db_route.route_name = row.get('route_name')
            db_route.origin = row.get('origin')
            db_route.destination = row.get('destination')
            db_route.active = parse_bool(row.get('active', 'True'))
            db_route.data_source = row.get('data_source', 'DEMO')
            db_route.valid_from = row.get('valid_from')
            db_route.valid_until = row.get('valid_until')
            source_counts[db_route.data_source] += 1

        db.flush()

        # Group Route Stops
        grouped_stops = defaultdict(list)
        for row in route_stops_data:
            grouped_stops[row['route_id']].append((int(row['stop_sequence']), row))

        # 3. Route Stops and Segments
        for route_id, stops in grouped_stops.items():
            stops.sort(key=lambda x: x[0])
            db.query(RouteStop).filter_by(route_id=route_id).delete()
            db.query(RouteSegment).filter_by(route_id=route_id).delete()
            db.flush()

            for seq, row in stops:
                lat = row.get('latitude')
                lon = row.get('longitude')
                stop = RouteStop(
                    route_id=route_id,
                    stop_id=str(uuid.uuid4()),
                    stop_sequence=seq,
                    stop_name=row['stop_name'],
                    latitude=float(lat) if lat else None,
                    longitude=float(lon) if lon else None
                )
                db.add(stop)
                source_counts[row.get('data_source', 'DEMO')] += 1
            
            for i in range(len(stops) - 1):
                seg = RouteSegment(
                    segment_id=f"{route_id}_{i+1}",
                    route_id=route_id,
                    from_stop=stops[i][1]['stop_name'],
                    to_stop=stops[i+1][1]['stop_name'],
                    sequence=stops[i][0]
                )
                db.add(seg)
                
        db.flush()

        # 4. Upsert Schedules
        for row in schedules_data:
            schedule_id = row['schedule_id']
            db_sch = db.query(Schedule).filter_by(schedule_id=schedule_id).first()
            if not db_sch:
                db_sch = Schedule(schedule_id=schedule_id)
                db.add(db_sch)
            db_sch.bus_id = row['bus_id']
            db_sch.route_id = row['route_id']
            db_sch.service_date = row.get('service_date')
            db_sch.departure_time = row.get('departure_time')
            db_sch.arrival_time = row.get('arrival_time')
            db_sch.active = parse_bool(row.get('active', 'True'))
            db_sch.data_source = row.get('data_source', 'DEMO')
            db_sch.valid_from = row.get('valid_from')
            db_sch.valid_until = row.get('valid_until')
            source_counts[db_sch.data_source] += 1

        db.flush()

        # 5. Upsert Capacity
        for row in parcel_cap_data:
            route_id = row['route_id']
            from_stop = row['from_stop']
            to_stop = row['to_stop']
            
            segment = db.query(RouteSegment).filter_by(
                route_id=route_id, from_stop=from_stop, to_stop=to_stop
            ).first()
            
            if segment:
                cap_id = f"{row['schedule_id']}_{segment.segment_id}"
                db_cap = db.query(ParcelCapacity).filter_by(capacity_id=cap_id).first()
                if not db_cap:
                    db_cap = ParcelCapacity(capacity_id=cap_id)
                    db.add(db_cap)
                db_cap.bus_id = row['bus_id']
                db_cap.schedule_id = row['schedule_id']
                db_cap.segment_id = segment.segment_id
                db_cap.max_safe_parcel_capacity_kg = float(row.get('max_safe_capacity_kg', 0))
                db_cap.reserved_capacity_kg = float(row.get('reserved_capacity_kg', 0))
                db_cap.data_source = row.get('data_source', 'DEMO')
                source_counts[db_cap.data_source] += 1

        db.flush()
        
        return {
            "success": True,
            "counts": {
                "buses": len(buses_data),
                "routes": len(routes_data),
                "route_stops": len(route_stops_data),
                "schedules": len(schedules_data),
                "capacities": len(parcel_cap_data)
            },
            "source_counts": dict(source_counts)
        }
