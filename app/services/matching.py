from sqlalchemy.orm import Session
from app.models.domain import Route, RouteStop, Schedule, Bus, TrafficEvent
from app.schemas.domain import LogisticsSearchRequest, LogisticsSearchResponse, LogisticsRecommendation
from app.services.capacity import CapacityService
from datetime import datetime

class LogisticsMatchingService:
    @staticmethod
    def find_matches(db: Session, request: LogisticsSearchRequest) -> LogisticsSearchResponse:
        # Request context for response
        req_context = {
            "source": request.source,
            "destination": request.destination,
            "date": request.date,
            "time": request.time,
            "weight_kg": request.weight_kg,
            "item_type": request.item_type
        }

        # Step 2: Find route compatibility
        # We need routes that have both source and dest, and source sequence < dest sequence
        routes = db.query(Route).filter(Route.active == True).all()
        compatible_routes = []
        for route in routes:
            stops = sorted(route.route_stops, key=lambda s: s.stop_sequence)
            source_seq = -1
            dest_seq = -1
            for stop in stops:
                if stop.stop_name.lower() == request.source.lower():
                    source_seq = stop.stop_sequence
                elif stop.stop_name.lower() == request.destination.lower():
                    dest_seq = stop.stop_sequence
            
            if source_seq != -1 and dest_seq != -1 and source_seq < dest_seq:
                compatible_routes.append(route)
                
        if not compatible_routes:
            return LogisticsSearchResponse(
                request=req_context,
                status="NO_MATCH",
                reason="No active route found connecting source to destination in the correct direction."
            )
            
        route_ids = [r.route_id for r in compatible_routes]

        # Step 3: Find Schedules
        schedules = db.query(Schedule).filter(
            Schedule.route_id.in_(route_ids),
            Schedule.service_date == request.date,
            Schedule.active == True
        ).all()
        
        if not schedules:
            return LogisticsSearchResponse(
                request=req_context,
                status="NO_MATCH",
                reason="No schedule found for the specified date on compatible routes."
            )

        recommendations = []
        
        for schedule in schedules:
            reasons = []
            score = 100
            
            # Step 4: Bus Eligibility
            bus = schedule.bus
            if not bus:
                continue
                
            # If cargo requested, bus must be parcel enabled
            if request.weight_kg and request.weight_kg > 0:
                if not bus.parcel_enabled:
                    # Skip this bus, it cannot take parcels
                    continue
                reasons.append("Service is parcel-enabled.")
            else:
                reasons.append("Passenger search (parcel capability not required).")

            # Passenger safety check (Step 8 fallback)
            if bus.status.upper() in ["UNAVAILABLE", "MAINTENANCE", "UNSAFE"]:
                # Skip unsafe buses
                continue
                
            # Step 5 & 6: Segment-Aware Capacity Checking
            available_capacity = 0.0
            if request.weight_kg and request.weight_kg > 0:
                cap_check = CapacityService.check_segment_capacity(
                    db,
                    schedule.schedule_id,
                    schedule.route_id,
                    request.source,
                    request.destination,
                    request.weight_kg
                )
                
                if not cap_check["eligible"]:
                    # No capacity, skip
                    continue
                    
                available_capacity = cap_check["available_capacity"]
                reasons.append(f"{request.weight_kg} kg capacity available across all {cap_check['segments_checked']} required segments.")
            
            reasons.append("Direct route match.")
            
            # Step 9: Traffic
            # Check traffic for stops on this route between source and dest
            # For simplicity in MVP, we just check if any active traffic event matches the route's origin/destination or any stop.
            # In a real app, we'd check specific segment locations.
            route_obj = next((r for r in compatible_routes if r.route_id == schedule.route_id), None)
            traffic_penalty = 0
            has_traffic = False
            
            # We don't have location bounding boxes, so string matching for hackathon
            traffic_events = db.query(TrafficEvent).filter(TrafficEvent.active == True).all()
            for te in traffic_events:
                te_loc = te.location.lower()
                for stop in route_obj.route_stops:
                    if te_loc in stop.stop_name.lower():
                        traffic_penalty += 15
                        has_traffic = True
                        reasons.append(f"Traffic warning at {stop.stop_name}: {te.severity}")
                        break
            
            score -= traffic_penalty
            if not has_traffic:
                reasons.append("No active traffic warning.")

            # Time proximity
            if request.time:
                # Basic string comparison or parse
                try:
                    req_t = datetime.strptime(request.time, "%H:%M")
                    dep_t = datetime.strptime(schedule.departure_time, "%H:%M")
                    diff_mins = abs((req_t - dep_t).total_seconds()) / 60
                    
                    if diff_mins <= 60:
                        reasons.append("Departure is within 1 hour of requested time.")
                    elif diff_mins <= 120:
                        score -= 5
                        reasons.append("Departure is within 2 hours of requested time.")
                    else:
                        score -= 10
                        reasons.append("Departure is outside requested time window.")
                except Exception:
                    pass

            recommendations.append(
                LogisticsRecommendation(
                    bus_id=bus.bus_id,
                    bus_number=bus.bus_number,
                    schedule_id=schedule.schedule_id,
                    route_id=schedule.route_id,
                    departure_time=schedule.departure_time,
                    arrival_time=schedule.arrival_time,
                    available_capacity_kg=available_capacity,
                    score=score,
                    reasons=reasons
                )
            )
            
        if not recommendations:
            return LogisticsSearchResponse(
                request=req_context,
                status="NO_MATCH",
                reason="Eligible schedules found, but they lacked sufficient parcel capacity, were unavailable, or lacked parcel capabilities."
            )
            
        # Step 10: Ranking
        # Sort by score descending
        recommendations.sort(key=lambda x: x.score, reverse=True)
        
        return LogisticsSearchResponse(
            request=req_context,
            status="MATCH_FOUND",
            recommendations=recommendations
        )
