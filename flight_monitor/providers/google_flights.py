from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime, timedelta
from typing import Optional

from fast_flights import FlightData, Passengers, get_flights

from flight_monitor.models import FlightOffer
from flight_monitor.providers.base import FlightProvider
from flight_monitor.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

SEAT_MAP = {
    "economy": "economy",
    "premium_economy": "premium-economy",
    "business": "business",
    "first": "first",
}


class GoogleFlightsProvider(FlightProvider):
    """Google Flights scraper via fast-flights library. No API key needed."""

    def __init__(self, rate_limiter: RateLimiter | None = None):
        # Be conservative to avoid anti-bot blocking
        self.rate_limiter = rate_limiter or RateLimiter(calls_per_second=0.5)

    def provider_name(self) -> str:
        return "google_flights"

    def search(
        self,
        origin: str,
        destination: str,
        departure_from: date,
        departure_to: date,
        return_nights_min: Optional[int],
        return_nights_max: Optional[int],
        trip_type: str,
        cabin_class: str,
        max_stopovers: int,
        adults: int,
        currency: str,
        max_results: int,
    ) -> list[FlightOffer]:
        """
        Search Google Flights by iterating over departure dates.
        For round-trip, pairs each departure date with middle stay duration.
        """
        seat = SEAT_MAP.get(cabin_class, "economy")
        passengers = Passengers(adults=adults)

        # Generate departure dates to search
        dep_dates = self._generate_search_dates(departure_from, departure_to)

        all_offers: list[FlightOffer] = []
        seen = set()

        for dep_date in dep_dates:
            if trip_type == "round_trip" and return_nights_min is not None:
                # Search with a representative return date (middle of stay range)
                mid_stay = (return_nights_min + return_nights_max) // 2
                ret_date = dep_date + timedelta(days=mid_stay)
                flight_data = [
                    FlightData(
                        date=dep_date.strftime("%Y-%m-%d"),
                        from_airport=origin,
                        to_airport=destination,
                    ),
                    FlightData(
                        date=ret_date.strftime("%Y-%m-%d"),
                        from_airport=destination,
                        to_airport=origin,
                    ),
                ]
                trip = "round-trip"
            else:
                flight_data = [
                    FlightData(
                        date=dep_date.strftime("%Y-%m-%d"),
                        from_airport=origin,
                        to_airport=destination,
                    ),
                ]
                trip = "one-way"
                ret_date = None

            self.rate_limiter.wait()

            try:
                logger.debug(
                    f"Google Flights: {origin}->{destination} {dep_date}"
                    + (f" return {ret_date}" if ret_date else "")
                )
                result = get_flights(
                    flight_data=flight_data,
                    trip=trip,
                    seat=seat,
                    passengers=passengers,
                    fetch_mode="fallback",
                )

                for flight in result.flights:
                    offer = self._parse_flight(
                        flight, origin, destination, dep_date, ret_date,
                        cabin_class, currency,
                    )
                    if offer is None:
                        continue

                    # Filter stopovers
                    if offer.stopovers > max_stopovers:
                        continue

                    # Deduplicate
                    key = (offer.airline, offer.departure_date, offer.price_original)
                    if key in seen:
                        continue
                    seen.add(key)
                    all_offers.append(offer)

            except Exception as e:
                logger.warning(f"Google Flights search failed for {dep_date}: {e}")
                continue

        all_offers.sort(key=lambda o: o.price_original)
        logger.info(f"Google Flights {origin}->{destination}: {len(all_offers)} offers")
        return all_offers[:max_results]

    def _generate_search_dates(self, dep_from: date, dep_to: date) -> list[date]:
        """
        Generate departure dates to search.
        Sample evenly to keep requests reasonable (max ~10 dates per route).
        """
        total_days = (dep_to - dep_from).days + 1
        max_searches = 10

        if total_days <= max_searches:
            return [dep_from + timedelta(days=i) for i in range(total_days)]

        # Sample evenly
        step = total_days / max_searches
        return [dep_from + timedelta(days=int(i * step)) for i in range(max_searches)]

    def _parse_flight(
        self,
        flight,
        origin: str,
        destination: str,
        dep_date: date,
        ret_date: date | None,
        cabin_class: str,
        currency: str,
    ) -> FlightOffer | None:
        """Parse a fast-flights Flight object into FlightOffer."""
        try:
            # Extract price and currency from string like "NT$3,306" or "$500"
            raw_price = str(flight.price) if hasattr(flight, "price") else ""
            detected_currency = _detect_currency(raw_price)
            price = _extract_price(raw_price)
            if price is None or price <= 0:
                return None

            # Extract stops count
            stops = 0
            if hasattr(flight, "stops") and flight.stops is not None:
                stops = int(flight.stops) if isinstance(flight.stops, (int, float)) else 0

            # Airline name
            airline_name = str(flight.name) if hasattr(flight, "name") else "Unknown"

            # Parse time strings like "6:45 PM on Wed, May 20"
            dep_time = _parse_gf_time(str(flight.departure)) if hasattr(flight, "departure") else ""
            arr_time = _parse_gf_time(str(flight.arrival)) if hasattr(flight, "arrival") else ""

            # Build Google Flights URL
            booking_url = (
                f"https://www.google.com/travel/flights?"
                f"q=Flights+from+{origin}+to+{destination}+on+{dep_date.isoformat()}"
            )

            return FlightOffer(
                provider="google_flights",
                airline=airline_name,
                airline_code=_lookup_airline_code(airline_name),
                origin=origin,
                destination=destination,
                departure_date=dep_date,
                return_date=ret_date,
                departure_time=dep_time,
                arrival_time=arr_time,
                return_departure_time=None,
                return_arrival_time=None,
                duration_outbound_minutes=_parse_duration(flight.duration)
                if hasattr(flight, "duration")
                else 0,
                duration_return_minutes=None,
                stopovers=stops,
                cabin_class=cabin_class,
                price_original=price,
                currency_original=detected_currency,
                price_display=price if detected_currency.upper() == currency.upper() else None,
                currency_display=currency if detected_currency.upper() == currency.upper() else None,
                booking_link=booking_url,
            )
        except Exception as e:
            logger.debug(f"Failed to parse flight: {e}")
            return None


# Currency symbol -> ISO code mapping
CURRENCY_SYMBOLS = {
    "NT$": "TWD",
    "RM": "MYR",
    "¥": "JPY",
    "JP¥": "JPY",
    "CN¥": "CNY",
    "₩": "KRW",
    "€": "EUR",
    "£": "GBP",
    "A$": "AUD",
    "C$": "CAD",
    "S$": "SGD",
    "HK$": "HKD",
    "₹": "INR",
    "฿": "THB",
    "₱": "PHP",
    "₫": "VND",
    "R$": "BRL",
    "$": "USD",  # Must be last — fallback for bare "$"
}


def _detect_currency(price_str: str) -> str:
    """Detect currency from price string like 'NT$3,306' or '€500'."""
    if not price_str:
        return "USD"
    # Check longer symbols first to avoid "$" matching "NT$"
    for symbol, code in CURRENCY_SYMBOLS.items():
        if symbol in price_str:
            return code
    return "USD"


def _extract_price(price_val) -> float | None:
    """Extract numeric price from various formats like 'NT$3,306'."""
    if price_val is None:
        return None
    if isinstance(price_val, (int, float)):
        return float(price_val)
    # Remove everything except digits and decimal point
    cleaned = re.sub(r"[^\d.]", "", str(price_val))
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def _parse_gf_time(time_str: str) -> str:
    """Parse Google Flights time like '6:45 PM on Wed, May 20' into '18:45'."""
    if not time_str:
        return ""
    # Extract the time portion before "on" (if present)
    match = re.match(r"(\d{1,2}:\d{2}\s*[APap][Mm])", time_str)
    if match:
        try:
            t = datetime.strptime(match.group(1).strip(), "%I:%M %p")
            return t.strftime("%H:%M")
        except ValueError:
            pass
    return time_str.split(" on ")[0] if " on " in time_str else time_str


def _parse_duration(duration_val) -> int:
    """Parse duration string like '4 hr 35 min' into minutes."""
    if not duration_val:
        return 0
    dur_str = str(duration_val).lower()
    hours = 0
    minutes = 0
    hr_match = re.search(r"(\d+)\s*(?:hr|h|hour)", dur_str)
    min_match = re.search(r"(\d+)\s*(?:min|m(?!o))", dur_str)
    if hr_match:
        hours = int(hr_match.group(1))
    if min_match:
        minutes = int(min_match.group(1))
    return hours * 60 + minutes


# Common airline name -> IATA code mapping
AIRLINE_CODES = {
    "airasia": "AK",
    "airasia x": "D7",
    "batik air": "OD",
    "batik air malaysia": "OD",
    "malaysia airlines": "MH",
    "malindo air": "OD",
    "firefly": "FY",
    "china airlines": "CI",
    "eva air": "BR",
    "starlux airlines": "JX",
    "starlux": "JX",
    "tigerair taiwan": "IT",
    "tigerair": "IT",
    "scoot": "TR",
    "singapore airlines": "SQ",
    "cathay pacific": "CX",
    "thai airways": "TG",
    "thai airasia x": "XJ",
    "japan airlines": "JL",
    "ana": "NH",
    "all nippon airways": "NH",
    "peach": "MM",
    "peach aviation": "MM",
    "jetstar": "3K",
    "jetstar japan": "GK",
    "jetstar asia": "3K",
    "korean air": "KE",
    "asiana airlines": "OZ",
    "vietnam airlines": "VN",
    "vietjet air": "VJ",
    "cebu pacific": "5J",
    "philippine airlines": "PR",
    "garuda indonesia": "GA",
    "lion air": "JT",
    "emirates": "EK",
    "qatar airways": "QR",
    "turkish airlines": "TK",
    "british airways": "BA",
    "lufthansa": "LH",
    "air france": "AF",
    "klm": "KL",
    "united airlines": "UA",
    "delta air lines": "DL",
    "american airlines": "AA",
    "air china": "CA",
    "china eastern": "MU",
    "china southern": "CZ",
    "spring airlines": "9C",
    "hainan airlines": "HU",
    "xiamen air": "MF",
    "air india": "AI",
    "indigo": "6E",
    "thai smile": "WE",
    "bangkok airways": "PG",
    "nok air": "DD",
    "air busan": "BX",
    "t'way air": "TW",
    "jin air": "LJ",
    "jeju air": "7C",
    "eastar jet": "ZE",
    "bamboo airways": "QH",
    "royal brunei": "BI",
    "air macau": "NX",
    "hong kong express": "UO",
    "greater bay airlines": "HB",
}


def _lookup_airline_code(airline_name: str) -> str:
    """Look up IATA code from airline name. Falls back to first 2 chars."""
    if not airline_name:
        return "??"
    key = airline_name.strip().lower()
    if key in AIRLINE_CODES:
        return AIRLINE_CODES[key]
    # Try partial match
    for name, code in AIRLINE_CODES.items():
        if name in key or key in name:
            return code
    return airline_name[:2].upper()
