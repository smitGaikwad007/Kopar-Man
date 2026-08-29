# Architecture

The Kopar-Man backend uses a modular, layered architecture common in FastAPI applications.

## Layers

- **API Layer (`app/api`)**: FastAPI routers and endpoints. Handles HTTP requests, input validation (via Pydantic).
- **Service Layer (`app/services`)**: Business logic. `LogisticsMatchingService` handles deterministic matching, and `CapacityService` manages parcel capacity logic.
- **Data Access Layer (`app/db`, `app/models`)**: SQLAlchemy ORM models and database session management.
- **Schemas (`app/schemas`)**: Pydantic models acting as Data Transfer Objects (DTOs) for the API layer.

## Single Source of Truth
The backend is explicitly designed to be the single source of truth for all operational data (buses, routes, schedules, parcel capacity, tracking). Integrations like n8n or Claude must query this backend and never invent data.

## Matching Pipeline
The `LogisticsMatchingService` implements an 8-step deterministic matching pipeline:
1. **Validate**: Pydantic validates input schemas (no negative weights, same source/dest).
2. **Route Match**: Verify source/destination stops exist on an active route in the correct direction.
3. **Schedule Match**: Check date and time proximity.
4. **Bus Eligibility**: Filter passenger vs. parcel buses depending on cargo weight.
5. **Capacity Check**: Utilize `CapacityService` for safe, segment-aware capacity checking.
6. **No Reservation**: Search strictly reads capacity, no reservation occurs here.
7. **Passenger Load**: Read passenger constraints if present in the database.
8. **Traffic**: Apply ranking penalties for active traffic events at matching stops.
9. **Ranking**: Produce an explainable score for the chatbot.
