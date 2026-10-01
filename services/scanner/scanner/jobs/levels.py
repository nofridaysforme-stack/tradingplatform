"""Compute, store, and print levels for checking by hand.

    python -m scanner.jobs.levels [--day YYYY-MM-DD] [--instrument EUR/USD]

Default day: the current New York trading day.
"""

import argparse
import json
from datetime import date

from scanner import db
from scanner.config import Settings
from scanner.data.sync import now_utc
from scanner.levels.compute import compute_and_store
from scanner.main import configure_logging
from scanner.time import trading_day_of


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m scanner.jobs.levels")
    parser.add_argument("--day", type=date.fromisoformat)
    parser.add_argument("--instrument")
    args = parser.parse_args(argv)

    configure_logging()
    settings = Settings()  # values come from the environment
    day: date = args.day or trading_day_of(now_utc())
    with db.make_pool(settings.database_url, max_size=1) as pool, pool.connection() as conn:
        conn.autocommit = True
        db.check_schema(conn)
        hol = db.holidays(conn, "forex")
        instruments = (
            [db.get_instrument(conn, args.instrument)]
            if args.instrument
            else db.list_instruments(conn)
        )
        for inst in instruments:
            sets = compute_and_store(conn, inst, day, hol)
            print(json.dumps({"instrument": inst.symbol, "trading_day": day.isoformat(), **sets}))


if __name__ == "__main__":
    main()
