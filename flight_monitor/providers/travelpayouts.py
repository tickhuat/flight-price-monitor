from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

import requests

from flight_monitor.models import FlightOffer
from flight_monitor.providers.base import FlightProvider
from flight_monitor.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

CALENDAR_URL = "https://api.travelpayouts.com/v1/prices/calendar"
DIRECT_URL = "https://api.travelpayouts.com/v1/prices/direct"
CHEAP_URL = "https://api.travelpayouts.com/v1/prices/cheap"

TRIP_CLASS_MAP = {
    "economy": 0,
    "premium_economy": 1,
    "business": 2,
    "first": 3,
}


class TravelpayoutsProvider(FlightProvider):
    """Travelpayouts API client — free cached flight price data."""

    def __init__(self, api_token: str, rate_limiter: RateLimiter | None = None):
        self.api_token = api_token
        self.rate_limiter = rate_limiter or RateLimiter(calls_per_second=5.0)

    def provider_name(self) -> str:
        return "travelpayouts"

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
        """
        Search Travelpayouts for cheap flights.
        Uses calendar endpoint for flexible dates, direct endpoint for non-stop filter.
        """
        all_offers: list[FlightOffer] = []

        # Determine which months to search
        months = self._get_months(departure_from, departure_to)

        for month in months:
            self.rate_limiter.wait()
            try:
                if max_stopovers == 0:
                    offers = self._search_direct(
                        origin, destination, month, trip_type,
                        return_date_from, return_date_to, currency,
                    )
                else:
                    offers = self._search_calendar(
                        origin, destination, month, trip_type,
                        return_date_from, return_date_to, cabin_class, currency,
                    )
                all_offers.extend(offers)
            except Exception as e:
                logger.warning(f"Travelpayouts search failed for {month}: {e}")

        # Filter by departure date range
        all_offers = [
            o for o in all_offers
            if o.departure_date and departure_from <= o.departure_date <= departure_to
        ]

        # Filter by return date range for round-trip
        if trip_type == "round_trip" and return_date_from is not None:
            all_offers = [
                o for o in all_offers
                if o.return_date
                and return_date_from <= o.return_date <= return_date_to
            ]

        all_offers.sort(key=lambda o: o.price_original)
        logger.info(f"Travelpayouts {origin}->{destination}: {len(all_offers)} offers")
        return all_offers[:max_results]

    def _search_calendar(
        self,
        origin: str,
        destination: str,
        month: str,
        trip_type: str,
        return_date_from: date | None,
        return_date_to: date | None,
        cabin_class: str,
        currency: str,
    ) -> list[FlightOffer]:
        """Use calendar endpoint to get prices for each day in a month."""
        params = {
            "origin": origin,
            "destination": destination,
            "depart_date": month,
            "calendar_type": "departure_date",
            "currency": currency.lower(),
            "trip_class": TRIP_CLASS_MAP.get(cabin_class, 0),
            "token": self.api_token,
        }

        if trip_type == "round_trip" and return_date_from is not None:
            # Use the return date range's middle month
            mid_days = (return_date_to - return_date_from).days // 2
            ret_mid = return_date_from + timedelta(days=mid_days)
            params["return_date"] = ret_mid.strftime("%Y-%m")

        resp = requests.get(CALENDAR_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            logger.warning(f"Travelpayouts calendar response: {data.get('error')}")
            return []

        offers = []
        for date_str, info in data.get("data", {}).items():
            offer = self._parse_offer(info, date_str, origin, destination, currency)
            if offer:
                offers.append(offer)

        return offers

    def _search_direct(
        self,
        origin: str,
        destination: str,
        month: str,
        trip_type: str,
        return_date_from: date | None,
        return_date_to: date | None,
        currency: str,
    ) -> list[FlightOffer]:
        """Use direct endpoint for non-stop flights only."""
        params = {
            "origin": origin,
            "destination": destination,
            "depart_date": month,
            "currency": currency.lower(),
            "token": self.api_token,
        }

        if trip_type == "round_trip" and return_date_from is not None:
            mid_days = (return_date_to - return_date_from).days // 2
            ret_mid = return_date_from + timedelta(days=mid_days)
            params["return_date"] = ret_mid.strftime("%Y-%m")

        resp = requests.get(DIRECT_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            return []

        offers = []
        dest_data = data.get("data", {}).get(destination, {})
        for _key, info in dest_data.items():
            offer = self._parse_offer(info, None, origin, destination, currency)
            if offer:
                offer.stopovers = 0  # Direct endpoint guarantees non-stop
                offers.append(offer)

        return offers

    def _parse_offer(
        self,
        info: dict,
        date_str: str | None,
        origin: str,
        destination: str,
        currency: str,
    ) -> FlightOffer | None:
        """Parse a Travelpayouts price entry into FlightOffer."""
        try:
            price = info.get("price", 0)
            if not price or price <= 0:
                return None

            airline_code = info.get("airline", "??")
            transfers = info.get("transfers", 0)

            dep_at = info.get("departure_at", "")
            ret_at = info.get("return_at", "")

            dep_date = _parse_iso_date(dep_at) if dep_at else _parse_date_str(date_str)
            ret_date = _parse_iso_date(ret_at) if ret_at else None

            dep_time = _parse_iso_time(dep_at) if dep_at else ""
            ret_time = _parse_iso_time(ret_at) if ret_at else ""

            flight_number = info.get("flight_number", "")
            booking_url = (
                f"https://www.google.com/travel/flights?"
                f"q=Flights+from+{origin}+to+{destination}"
                + (f"+on+{dep_date.isoformat()}" if dep_date else "")
            )

            return FlightOffer(
                provider="travelpayouts",
                airline=airline_code,
                airline_code=airline_code,
                origin=origin,
                destination=destination,
                departure_date=dep_date,
                return_date=ret_date,
                departure_time=dep_time,
                arrival_time="",  # Not provided by Travelpayouts
                return_departure_time=ret_time if ret_time else None,
                return_arrival_time=None,
                duration_outbound_minutes=0,  # Not provided
                duration_return_minutes=None,
                stopovers=transfers,
                cabin_class="",
                price_original=float(price),
                currency_original=currency.upper(),
                price_display=float(price),
                currency_display=currency.upper(),
                booking_link=booking_url,
                raw_data=info,
            )
        except Exception as e:
            logger.debug(f"Failed to parse Travelpayouts offer: {e}")
            return None

    @staticmethod
    def _get_months(dep_from: date, dep_to: date) -> list[str]:
        """Get list of YYYY-MM strings covering the date range."""
        months = set()
        current = dep_from.replace(day=1)
        end = dep_to.replace(day=1)
        while current <= end:
            months.add(current.strftime("%Y-%m"))
            # Move to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
        return sorted(months)


# -- Helpers --

def _timedelta_months(n: int):
    """Return a timedelta approximation for n months."""
    from datetime import timedelta
    return timedelta(days=31 * n)


def _parse_iso_date(iso_str: str) -> date | None:
    if not iso_str:
        return None
    try:
        return datetime.fromisoformat(iso_str.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _parse_iso_time(iso_str: str) -> str:
    if not iso_str:
        return ""
    try:
        return datetime.fromisoformat(iso_str.replace("Z", "+00:00")).strftime("%H:%M")
    except ValueError:
        return ""


def _parse_date_str(date_str: str | None) -> date | None:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None
