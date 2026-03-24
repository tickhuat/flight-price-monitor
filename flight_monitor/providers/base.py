from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional

from flight_monitor.models import FlightOffer


class FlightProvider(ABC):
    """Abstract base class for flight data providers."""

    @abstractmethod
    def search(
        self,
        origin: str,
        destination: str,
        departure_from: date,
        departure_to: date,
        return_date_from: Optional[date],
        return_date_to: Optional[date],
        trip_type: str,
        cabin_class: str,
        max_stopovers: int,
        adults: int,
        currency: str,
        max_results: int,
    ) -> list[FlightOffer]:
        """Search for flights matching the given criteria."""
        ...

    @abstractmethod
    def provider_name(self) -> str:
        """Return provider identifier string."""
        ...
