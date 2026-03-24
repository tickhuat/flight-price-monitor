#!/usr/bin/env python3
"""Flight Price Monitor - Search for cheap flights and get email alerts."""

from __future__ import annotations

import argparse
import logging
import sys

from flight_monitor.config import ConfigError, load_config
from flight_monitor.engine import FlightMonitorEngine


def main():
    parser = argparse.ArgumentParser(
        description="Flight Price Monitor - Search for cheap flights and get email alerts"
    )
    parser.add_argument(
        "-c", "--config",
        default="config.yaml",
        help="Path to config file (default: config.yaml)",
    )
    parser.add_argument(
        "-e", "--env",
        default=".env",
        help="Path to .env file (default: .env)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Search and print results without sending email",
    )
    parser.add_argument(
        "--watch",
        type=str,
        help="Run only the named watch (exact name match)",
    )
    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Load config
    try:
        config = load_config(args.config, args.env)
    except ConfigError as e:
        logging.error(f"Configuration error: {e}")
        sys.exit(1)

    # Create engine
    engine = FlightMonitorEngine(config, dry_run=args.dry_run)

    # Filter to specific watch if requested
    if args.watch:
        engine.watches = [w for w in engine.watches if w.name == args.watch]
        if not engine.watches:
            logging.error(f"No watch found with name: {args.watch}")
            sys.exit(1)

    # Run
    logging.info(
        f"Starting flight monitor ({len(engine.watches)} watch(es), "
        f"{len(engine.providers)} provider(s), "
        f"dry_run={args.dry_run})"
    )

    results = engine.run()

    # Print summary
    print(f"\n{'=' * 40}")
    print("SUMMARY")
    print(f"{'=' * 40}")
    has_errors = False
    for r in results:
        status = f"{len(r.offers_under_threshold)} deals" if r.offers_under_threshold else "no deals"
        print(f"  [{r.watch_name}] {r.offers_found} found, {status}")
        if r.errors:
            has_errors = True
            for e in r.errors:
                print(f"    ERROR: {e}")

    sys.exit(1 if has_errors else 0)


if __name__ == "__main__":
    main()
