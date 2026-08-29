from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime

class NormalizedTransportData(BaseModel):
    buses: List[Dict[str, Any]]
    routes: List[Dict[str, Any]]
    route_stops: List[Dict[str, Any]]
    schedules: List[Dict[str, Any]]
    parcel_capacity: List[Dict[str, Any]]

class TransportDataProvider(ABC):
    """
    Base interface for external transport data providers.
    """
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the unique name of the provider."""
        pass

    @abstractmethod
    def fetch_all_data(self) -> NormalizedTransportData:
        """
        Fetch data from the external provider and normalize it to Kopar-Man's 
        internal dictionaries matching the CSV import structures.
        """
        pass
