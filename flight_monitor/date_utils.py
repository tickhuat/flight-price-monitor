from __future__ import annotations

from datetime import date, timedelta
from typing import Iterator


def generate_date_pairs(
    dep_from: date,
    dep_to: date,
    stay_min: int,
    stay_max: int,
) -> list[tuple[date, date]]:
    """
    Generate all (departure_date, return_date) pairs within the given ranges.
    Used for providers that don't support native flexible date searching (e.g. Amadeus).
    """
    pairs = []
    current = dep_from
    while current <= dep_to:
        for nights in range(stay_min, stay_max + 1):
            ret = current + timedelta(days=nights)
            pairs.append((current, ret))
        current += timedelta(days=1)
    return pairs


def estimate_api_calls(
    dep_from: date,
    dep_to: date,
    stay_min: int,
    stay_max: int,
    num_origin_dest_pairs: int,
) -> int:
    """Estimate total API calls needed for full enumeration."""
    num_dep_days = (dep_to - dep_from).days + 1
    num_stay_options = stay_max - stay_min + 1
    return num_dep_days * num_stay_options * num_origin_dest_pairs


def sample_date_pairs(
    dep_from: date,
    dep_to: date,
    stay_min: int,
    stay_max: int,
    max_calls: int,
) -> list[tuple[date, date]]:
    """
    If full enumeration exceeds max_calls, sample evenly across the range.
    Returns at most max_calls pairs.
    """
    all_pairs = generate_date_pairs(dep_from, dep_to, stay_min, stay_max)
    if len(all_pairs) <= max_calls:
        return all_pairs

    step = len(all_pairs) / max_calls
    return [all_pairs[int(i * step)] for i in range(max_calls)]
