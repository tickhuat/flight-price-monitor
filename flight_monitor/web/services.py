from __future__ import annotations

import json
import logging
from datetime import datetime

from flight_monitor.currency import CurrencyConverter
from flight_monitor.models import FlightOffer, SearchResult, WatchConfig
from flight_monitor.providers.base import FlightProvider
from flight_monitor.providers.google_flights import GoogleFlightsProvider
from flight_monitor.providers.travelpayouts import TravelpayoutsProvider
from flight_monitor.rate_limiter import RateLimiter

from .database import FlightOfferRow, SearchRun, Setting, Watch, db

logger = logging.getLogger(__name__)


def db_watch_to_watch_config(w: Watch) -> WatchConfig:
    """Convert a SQLAlchemy Watch row to engine's WatchConfig dataclass."""
    return WatchConfig(
        name=w.name,
        enabled=w.enabled,
        origins=w.get_origins(),
        destinations=w.get_destinations(),
        trip_type=w.trip_type,
        departure_date_from=w.departure_date_from,
        departure_date_to=w.departure_date_to,
        return_date_from=w.return_date_from,
        return_date_to=w.return_date_to,
        cabin_classes=w.get_cabin_classes(),
        max_stopovers=w.max_stopovers,
        adults=w.adults,
        max_price=w.max_price,
        currency=w.currency,
        max_results=w.max_results,
    )


def build_providers() -> list[FlightProvider]:
    """Build provider list from DB settings."""
    providers = []
    settings = Setting.get_all()

    if settings.get("google_flights_enabled", "true") == "true":
        limiter = RateLimiter(calls_per_second=0.5)
        providers.append(GoogleFlightsProvider(limiter))

    if settings.get("travelpayouts_enabled", "false") == "true":
        token = settings.get("travelpayouts_token", "")
        if token:
            limiter = RateLimiter(calls_per_second=5.0)
            providers.append(TravelpayoutsProvider(token, limiter))

    return providers


def run_search_for_watch(watch_id: int, triggered_by: str = "manual") -> int:
    """Execute a search for a single watch. Returns search_run id."""
    watch = Watch.query.get(watch_id)
    if not watch:
        raise ValueError(f"Watch {watch_id} not found")

    # Create search run
    run = SearchRun(
        watch_id=watch_id,
        status="running",
        started_at=datetime.utcnow(),
        triggered_by=triggered_by,
    )
    db.session.add(run)
    db.session.commit()

    try:
        watch_config = db_watch_to_watch_config(watch)
        providers = build_providers()
        currency_converter = CurrencyConverter()

        all_offers: list[FlightOffer] = []
        errors: list[str] = []

        for provider in providers:
            for origin in watch_config.origins:
                for destination in watch_config.destinations:
                    for cabin_class in watch_config.cabin_classes:
                        try:
                            offers = provider.search(
                                origin=origin,
                                destination=destination,
                                departure_from=watch_config.departure_date_from,
                                departure_to=watch_config.departure_date_to,
                                return_date_from=watch_config.return_date_from,
                                return_date_to=watch_config.return_date_to,
                                trip_type=watch_config.trip_type,
                                cabin_class=cabin_class,
                                max_stopovers=watch_config.max_stopovers,
                                adults=watch_config.adults,
                                currency=watch_config.currency,
                                max_results=watch_config.max_results,
                            )
                            all_offers.extend(offers)
                        except Exception as e:
                            msg = f"{provider.provider_name()} {origin}->{destination} {cabin_class}: {e}"
                            logger.warning(msg)
                            errors.append(msg)

        # Currency conversion
        for offer in all_offers:
            if (
                offer.currency_original
                and offer.currency_original.upper() != watch_config.currency.upper()
            ):
                try:
                    offer.price_display = currency_converter.convert(
                        offer.price_original,
                        offer.currency_original,
                        watch_config.currency,
                    )
                    offer.currency_display = watch_config.currency
                except Exception as e:
                    logger.warning(f"Currency conversion failed: {e}")
                    offer.price_display = offer.price_original
                    offer.currency_display = offer.currency_original

        # Store offers in DB
        matched = 0
        for offer in all_offers:
            is_under = (
                offer.price_display is not None
                and offer.price_display <= watch_config.max_price
            )
            if is_under:
                matched += 1

            row = FlightOfferRow(
                search_run_id=run.id,
                provider=offer.provider,
                airline=offer.airline,
                airline_code=offer.airline_code,
                origin=offer.origin,
                destination=offer.destination,
                departure_date=offer.departure_date,
                return_date=offer.return_date,
                departure_time=offer.departure_time,
                arrival_time=offer.arrival_time,
                return_departure_time=offer.return_departure_time,
                return_arrival_time=offer.return_arrival_time,
                duration_outbound_minutes=offer.duration_outbound_minutes,
                duration_return_minutes=offer.duration_return_minutes,
                stopovers=offer.stopovers,
                cabin_class=offer.cabin_class,
                price_original=offer.price_original,
                currency_original=offer.currency_original,
                price_display=offer.price_display,
                currency_display=offer.currency_display,
                booking_link=offer.booking_link,
                is_under_threshold=is_under,
            )
            db.session.add(row)

        run.status = "completed"
        run.completed_at = datetime.utcnow()
        run.offers_found = len(all_offers)
        run.offers_matched = matched
        run.set_errors(errors)
        db.session.commit()

    except Exception as e:
        logger.error(f"Search failed for watch {watch_id}: {e}")
        run.status = "failed"
        run.completed_at = datetime.utcnow()
        run.set_errors([str(e)])
        db.session.commit()

    return run.id
