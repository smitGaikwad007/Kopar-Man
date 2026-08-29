from sqlalchemy.orm import Session
from typing import Dict, Any, Type
from app.services.transport_providers.base import TransportDataProvider
from app.services.transport_providers.etravos import EtravosProvider
from app.services.ingestion import TransportIngestionService

class ProviderSyncService:
    _providers: Dict[str, Type[TransportDataProvider]] = {
        "etravos": EtravosProvider
    }

    @classmethod
    def get_provider(cls, name: str) -> TransportDataProvider:
        provider_class = cls._providers.get(name.lower())
        if not provider_class:
            raise ValueError(f"Provider '{name}' is not supported.")
        return provider_class()

    @classmethod
    def sync(cls, db: Session, provider_name: str) -> Dict[str, Any]:
        """
        Synchronizes data from the specified provider into the database safely.
        Uses transaction safety.
        """
        provider = cls.get_provider(provider_name)
        
        # 1. Fetch
        normalized_data = provider.fetch_all_data()

        buses = normalized_data.buses
        routes = normalized_data.routes
        route_stops = normalized_data.route_stops
        schedules = normalized_data.schedules
        parcel_cap = normalized_data.parcel_capacity

        # Ensure everything is valid before touching DB
        # 2. Validate
        errors = TransportIngestionService.validate_data(
            buses, routes, route_stops, schedules, parcel_cap
        )

        if errors:
            return {
                "success": False,
                "reason": "Validation failed on provider data.",
                "errors": errors
            }

        # 3. Upsert with transaction safety
        try:
            result = TransportIngestionService.upsert_data(
                db=db,
                buses_data=buses,
                routes_data=routes,
                route_stops_data=route_stops,
                schedules_data=schedules,
                parcel_cap_data=parcel_cap
            )
            db.commit()
            return result
        except Exception as e:
            db.rollback()
            return {
                "success": False,
                "reason": f"Database error during upsert: {str(e)}"
            }
