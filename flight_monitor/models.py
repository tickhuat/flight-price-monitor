from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass
class FlightOffer:
    """A single flight offer returned by a provider."""

    provider: str  # "kiwi" or "amadeus"
    airline: str  # e.g. "China Airlines"
    airline_code: str  # e.g. "CI"
    origin: str  # IATA code
    destination: str  # IATA code

    departure_date: date
    return_date: Optional[date]  # None for one-way

    departure_time: str  # "14:30"
    arrival_time: str  # "19:45"
    return_departure_time: Optional[str]
    return_arrival_time: Optional[str]

    duration_outbound_minutes: int
    duration_return_minutes: Optional[int]

    stopovers: int
    cabin_class: str

    price_original: float  # Price in API's returned currency
    currency_original: str  # e.g. "EUR"
    price_display: Optional[float]  # Converted to display currency
    currency_display: Optional[str]  # e.g. "TWD"

    booking_link: str
    raw_data: Optional[dict] = field(default=None, repr=False)


@dataclass
class WatchConfig:
    """Parsed configuration for a single flight watch."""

    name: str
    enabled: bool
    origins: list[str]
    destinations: list[str]
    trip_type: str  # "one_way" or "round_trip"

    departure_date_from: date
    departure_date_to: date

    stay_nights_min: Optional[int]  # round_trip only
    stay_nights_max: Optional[int]

    cabin_class: str  # economy / premium_economy / business / first
    max_stopovers: int
    adults: int

    max_price: float
    currency: str  # display currency for this watch
    max_results: int


@dataclass
class SearchResult:
    """Result of processing one watch."""

    watch_name: str
    offers_found: int  # total from API before filtering
    offers_under_threshold: list[FlightOffer]
    errors: list[str]
    searched_at: datetime
