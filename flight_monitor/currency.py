from __future__ import annotations

import logging
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

CURRENCY_API_URL = (
    "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/{base}.json"
)
CURRENCY_API_FALLBACK = (
    "https://latest.currency-api.pages.dev/v1/currencies/{base}.json"
)

CACHE_TTL_SECONDS = 43200  # 12 hours


class CurrencyError(Exception):
    pass


class CurrencyConverter:
    """Convert between currencies using fawazahmed0/exchange-api (no API key needed)."""

    def __init__(self):
        self._cache: dict[str, dict[str, float]] = {}  # base -> {target: rate}
        self._cache_time: datetime | None = None

    def convert(self, amount: float, from_currency: str, to_currency: str) -> float:
        """Convert amount from one currency to another."""
        if from_currency.upper() == to_currency.upper():
            return amount
        rate = self.get_rate(from_currency, to_currency)
        return round(amount * rate, 2)

    def get_rate(self, from_currency: str, to_currency: str) -> float:
        """Get exchange rate from from_currency to to_currency."""
        if from_currency.upper() == to_currency.upper():
            return 1.0

        base = from_currency.lower()
        if base not in self._cache or self._is_stale():
            self._fetch_rates(base)

        target = to_currency.lower()
        rates = self._cache.get(base, {})
        if target not in rates:
            raise CurrencyError(f"Unknown currency: {to_currency}")
        return rates[target]

    def _fetch_rates(self, base: str):
        """Fetch rates from API with fallback URL."""
        for url_template in [CURRENCY_API_URL, CURRENCY_API_FALLBACK]:
            try:
                url = url_template.format(base=base)
                resp = requests.get(url, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                self._cache[base] = data.get(base, {})
                self._cache_time = datetime.now()
                logger.debug(f"Fetched exchange rates for {base.upper()}")
                return
            except requests.RequestException as e:
                logger.warning(f"Currency API failed ({url_template}): {e}")
                continue
        raise CurrencyError(f"Failed to fetch exchange rates for {base.upper()}")

    def _is_stale(self) -> bool:
        if not self._cache_time:
            return True
        return (datetime.now() - self._cache_time).total_seconds() > CACHE_TTL_SECONDS
