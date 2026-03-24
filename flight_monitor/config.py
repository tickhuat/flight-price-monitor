from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

from flight_monitor.models import WatchConfig

VALID_CABIN_CLASSES = {"economy", "premium_economy", "business", "first"}
VALID_TRIP_TYPES = {"one_way", "round_trip"}


class ConfigError(Exception):
    pass


def load_config(config_path: str = "config.yaml", env_path: str = ".env") -> dict:
    """Load and validate config.yaml, merge with .env secrets."""
    # Load .env
    env_file = Path(env_path)
    if env_file.exists():
        load_dotenv(env_file)

    # Load YAML
    config_file = Path(config_path)
    if not config_file.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    with open(config_file, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not config:
        raise ConfigError("Config file is empty")

    # Validate required sections
    if "email" not in config or "recipient" not in config.get("email", {}):
        raise ConfigError("Missing email.recipient in config")

    if "watches" not in config or not config["watches"]:
        raise ConfigError("No watches defined in config")

    # Inject env vars into config for convenience
    config["_env"] = {
        "TRAVELPAYOUTS_TOKEN": os.getenv("TRAVELPAYOUTS_TOKEN", ""),
        "SMTP_HOST": os.getenv("SMTP_HOST", "smtp.gmail.com"),
        "SMTP_PORT": int(os.getenv("SMTP_PORT", "587")),
        "SMTP_USER": os.getenv("SMTP_USER", ""),
        "SMTP_PASSWORD": os.getenv("SMTP_PASSWORD", ""),
        "EMAIL_FROM": os.getenv("EMAIL_FROM", os.getenv("SMTP_USER", "")),
    }

    return config


def parse_watches(config: dict) -> list[WatchConfig]:
    """Convert raw config dicts to WatchConfig dataclasses. Returns only enabled watches."""
    global_currency = config.get("currency", {}).get("display", "USD")
    watches = []
    errors = []

    for i, raw in enumerate(config.get("watches", [])):
        name = raw.get("name", f"watch_{i}")

        if not raw.get("enabled", True):
            continue

        try:
            watch = _parse_single_watch(raw, global_currency)
            watches.append(watch)
        except (ValueError, KeyError) as e:
            errors.append(f"Watch '{name}': {e}")

    if errors:
        raise ConfigError("Config validation errors:\n  " + "\n  ".join(errors))

    if not watches:
        raise ConfigError("No enabled watches found in config")

    return watches


def _parse_single_watch(raw: dict, global_currency: str) -> WatchConfig:
    """Parse and validate a single watch config dict."""
    # Required fields
    name = raw["name"]
    origins = raw.get("origins", [])
    destinations = raw.get("destinations", [])

    if not origins:
        raise ValueError("origins is empty")
    if not destinations:
        raise ValueError("destinations is empty")

    # Trip type
    trip_type = raw.get("trip_type", "round_trip")
    if trip_type not in VALID_TRIP_TYPES:
        raise ValueError(f"Invalid trip_type '{trip_type}', must be one of {VALID_TRIP_TYPES}")

    # Dates
    dep_from = _parse_date(raw.get("departure_date_from", ""), "departure_date_from")
    dep_to = _parse_date(raw.get("departure_date_to", ""), "departure_date_to")
    if dep_to < dep_from:
        raise ValueError("departure_date_to must be >= departure_date_from")

    # Stay nights (required for round_trip)
    stay_min = raw.get("stay_nights_min")
    stay_max = raw.get("stay_nights_max")
    if trip_type == "round_trip":
        if stay_min is None or stay_max is None:
            raise ValueError("stay_nights_min and stay_nights_max are required for round_trip")
        if stay_max < stay_min:
            raise ValueError("stay_nights_max must be >= stay_nights_min")

    # Cabin class
    cabin_class = raw.get("cabin_class", "economy")
    if cabin_class not in VALID_CABIN_CLASSES:
        raise ValueError(f"Invalid cabin_class '{cabin_class}', must be one of {VALID_CABIN_CLASSES}")

    # Other fields
    max_stopovers = raw.get("max_stopovers", 0)
    adults = raw.get("adults", 1)
    max_price = raw.get("max_price")
    if max_price is None:
        raise ValueError("max_price is required")

    currency = raw.get("currency", global_currency)
    max_results = raw.get("max_results", 20)

    return WatchConfig(
        name=name,
        enabled=True,
        origins=origins,
        destinations=destinations,
        trip_type=trip_type,
        departure_date_from=dep_from,
        departure_date_to=dep_to,
        stay_nights_min=stay_min,
        stay_nights_max=stay_max,
        cabin_class=cabin_class,
        max_stopovers=max_stopovers,
        adults=adults,
        max_price=float(max_price),
        currency=currency,
        max_results=max_results,
    )


def _parse_date(value: str, field_name: str) -> date:
    """Parse a YYYY-MM-DD date string."""
    if not value:
        raise ValueError(f"{field_name} is required")
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"{field_name} must be in YYYY-MM-DD format, got '{value}'")
