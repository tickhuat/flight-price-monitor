from __future__ import annotations

import functools
import logging
import time
from datetime import datetime

import requests

from flight_monitor.config import load_config, parse_watches
from flight_monitor.currency import CurrencyConverter
from flight_monitor.models import FlightOffer, SearchResult, WatchConfig
from flight_monitor.notifier import EmailNotifier
from flight_monitor.providers.base import FlightProvider
from flight_monitor.providers.google_flights import GoogleFlightsProvider
from flight_monitor.providers.travelpayouts import TravelpayoutsProvider
from flight_monitor.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


def retry_on_failure(max_retries: int = 1, backoff_base: float = 2.0):
    """Decorator that retries on RequestException with exponential backoff."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except requests.RequestException as e:
                    last_exc = e
                    if attempt < max_retries:
                        sleep_time = backoff_base * (2**attempt)
                        logger.warning(
                            f"Retry {attempt + 1}/{max_retries} after {sleep_time}s: {e}"
                        )
                        time.sleep(sleep_time)
            raise last_exc

        return wrapper

    return decorator


class FlightMonitorEngine:
    """Main orchestrator: ties providers, filtering, currency, notification."""

    def __init__(self, config: dict, dry_run: bool = False):
        self.config = config
        self.dry_run = dry_run
        self.watches = parse_watches(config)
        self.providers = self._init_providers(config)
        self.currency = CurrencyConverter()
        self.notifier = self._init_notifier(config) if not dry_run else None

    def _init_providers(self, config: dict) -> list[FlightProvider]:
        """Initialize enabled providers based on config."""
        providers = []
        env = config.get("_env", {})
        provider_configs = config.get("providers", [])

        # Rate limiters
        gf_limiter = RateLimiter(calls_per_second=0.5)  # Conservative for scraping
        tp_limiter = RateLimiter(calls_per_second=5.0)

        for pc in provider_configs:
            if not pc.get("enabled", False):
                continue

            name = pc.get("name", "")

            if name == "google_flights":
                providers.append(GoogleFlightsProvider(gf_limiter))
                logger.info("Google Flights provider initialized (no API key needed)")

            elif name == "travelpayouts":
                token = env.get("TRAVELPAYOUTS_TOKEN", "")
                if not token:
                    logger.warning(
                        "Travelpayouts enabled but TRAVELPAYOUTS_TOKEN not set, skipping"
                    )
                    continue
                providers.append(TravelpayoutsProvider(token, tp_limiter))
                logger.info("Travelpayouts provider initialized")
            else:
                logger.warning(f"Unknown provider: {name}")

        if not providers:
            logger.error("No providers available! Check your .env and config.yaml")

        return providers

    def _init_notifier(self, config: dict) -> EmailNotifier | None:
        env = config.get("_env", {})
        smtp_user = env.get("SMTP_USER", "")
        smtp_password = env.get("SMTP_PASSWORD", "")
        if not smtp_user or not smtp_password:
            logger.warning("SMTP credentials not set, email notifications disabled")
            return None

        return EmailNotifier(
            smtp_host=env.get("SMTP_HOST", "smtp.gmail.com"),
            smtp_port=env.get("SMTP_PORT", 587),
            username=smtp_user,
            password=smtp_password,
            from_addr=env.get("EMAIL_FROM", smtp_user),
        )

    def run(self) -> list[SearchResult]:
        """Execute all enabled watches, collect results, send notifications."""
        results = []

        for watch in self.watches:
            logger.info(f"Processing watch: {watch.name}")
            try:
                result = self._process_watch(watch)
                results.append(result)
                if result.offers_under_threshold:
                    logger.info(
                        f"  {len(result.offers_under_threshold)} deals under "
                        f"{watch.currency} {watch.max_price:,.0f}"
                    )
                else:
                    logger.info(f"  No deals under threshold ({result.offers_found} total offers)")
            except Exception as e:
                logger.error(f"Watch '{watch.name}' failed: {e}")
                results.append(
                    SearchResult(
                        watch_name=watch.name,
                        offers_found=0,
                        offers_under_threshold=[],
                        errors=[str(e)],
                        searched_at=datetime.now(),
                    )
                )

        # Send email if not dry-run
        if self.notifier:
            recipient = self.config["email"]["recipient"]
            sent = self.notifier.send_alert(recipient, results)
            if sent:
                logger.info(f"Email alert sent to {recipient}")
        else:
            # Dry-run: print deals to stdout
            self._print_results(results)

        return results

    def _process_watch(self, watch: WatchConfig) -> SearchResult:
        """Process a single watch: search all providers, convert currency, filter."""
        all_offers: list[FlightOffer] = []
        errors: list[str] = []

        for provider in self.providers:
            for origin in watch.origins:
                for destination in watch.destinations:
                    for cabin_class in watch.cabin_classes:
                        try:
                            offers = self._search_with_retry(
                                provider, origin, destination, watch, cabin_class
                            )
                            all_offers.extend(offers)
                        except Exception as e:
                            msg = f"{provider.provider_name()} {origin}->{destination} {cabin_class}: {e}"
                            logger.warning(msg)
                            errors.append(msg)

        # Currency conversion for offers not in display currency
        for offer in all_offers:
            if (
                offer.currency_original
                and offer.currency_original.upper() != watch.currency.upper()
            ):
                try:
                    offer.price_display = self.currency.convert(
                        offer.price_original,
                        offer.currency_original,
                        watch.currency,
                    )
                    offer.currency_display = watch.currency
                except Exception as e:
                    logger.warning(f"Currency conversion failed: {e}")
                    # Keep original price
                    offer.price_display = offer.price_original
                    offer.currency_display = offer.currency_original

        # Filter by price threshold
        under_threshold = [
            o
            for o in all_offers
            if o.price_display is not None and o.price_display <= watch.max_price
        ]
        under_threshold.sort(key=lambda o: (o.price_display or 0))

        return SearchResult(
            watch_name=watch.name,
            offers_found=len(all_offers),
            offers_under_threshold=under_threshold,
            errors=errors,
            searched_at=datetime.now(),
        )

    @retry_on_failure(max_retries=1, backoff_base=2.0)
    def _search_with_retry(
        self,
        provider: FlightProvider,
        origin: str,
        destination: str,
        watch: WatchConfig,
        cabin_class: str,
    ) -> list[FlightOffer]:
        return provider.search(
            origin=origin,
            destination=destination,
            departure_from=watch.departure_date_from,
            departure_to=watch.departure_date_to,
            return_date_from=watch.return_date_from,
            return_date_to=watch.return_date_to,
            trip_type=watch.trip_type,
            cabin_class=cabin_class,
            max_stopovers=watch.max_stopovers,
            adults=watch.adults,
            currency=watch.currency,
            max_results=watch.max_results,
        )

    def _print_results(self, results: list[SearchResult]):
        """Print results to stdout (for dry-run or when email fails)."""
        for r in results:
            print(f"\n{'=' * 60}")
            print(f"Watch: {r.watch_name}")
            print(f"Searched at: {r.searched_at.strftime('%Y-%m-%d %H:%M')}")
            print(f"Total offers: {r.offers_found}")
            print(f"Deals under threshold: {len(r.offers_under_threshold)}")

            if r.errors:
                print("Errors:")
                for e in r.errors:
                    print(f"  - {e}")

            if r.offers_under_threshold:
                print(f"\n{'Airline':<30} {'Route':<15} {'Depart':<12} {'Return':<12} {'Time':<14} {'Duration':<10} {'Price':>12}")
                print("-" * 107)
                for o in r.offers_under_threshold:
                    currency = o.currency_display or o.currency_original
                    price = o.price_display if o.price_display is not None else o.price_original
                    route = f"{o.origin}->{o.destination}"
                    time_str = f"{o.departure_time}->{o.arrival_time}"
                    dur = f"{o.duration_outbound_minutes // 60}h{o.duration_outbound_minutes % 60:02d}m"
                    ret = str(o.return_date) if o.return_date else "-"
                    # Show full airline name + code
                    airline_display = f"{o.airline} ({o.airline_code})" if o.airline != o.airline_code else o.airline
                    print(
                        f"{airline_display:<30} {route:<15} {str(o.departure_date):<12} "
                        f"{ret:<12} {time_str:<14} {dur:<10} {currency} {price:>8,.0f}"
                    )
                    if o.booking_link:
                        print(f"{'':30} Book: {o.booking_link}")
