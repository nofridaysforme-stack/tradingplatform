"""APScheduler setup (spec 16). Times are UTC unless a trigger names America/New_York, which
handles daylight saving. Every job: max_instances=1, coalesce=True, and a job_runs row."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from apscheduler.schedulers.base import BaseScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from psycopg_pool import ConnectionPool

from scanner import db
from scanner.config import MASSIVE_HOST, Settings
from scanner.data.massive import MassiveClient
from scanner.data.oanda import OandaClient
from scanner.data.sync import refresh_universe
from scanner.jobs import forex_bar_close, forex_day_roll, stock_eod
from scanner.rules.registry import Registry
from scanner.time import NEW_YORK

log = logging.getLogger(__name__)

VERSION = "0.2.0"
BAR_RETRIES = (20, 40)  # seconds after the first attempt
STOCK_RETRY = timedelta(minutes=15)
STOCK_LAST_TRY_HOUR = 23  # New York
JOB_DEFAULTS = {"max_instances": 1, "coalesce": True, "misfire_grace_time": 60}


class Worker:
    def __init__(self, pool: ConnectionPool, settings: Settings, scheduler: BaseScheduler) -> None:
        self.pool = pool
        self.scheduler = scheduler
        with pool.connection() as conn:
            self.registry = Registry.load(conn)
        self.oanda = (
            OandaClient(settings.oanda_api_token.get_secret_value(), settings.oanda_host)
            if settings.oanda_api_token
            else None
        )
        self.massive = (
            MassiveClient(settings.massive_api_key.get_secret_value(), MASSIVE_HOST)
            if settings.massive_api_key
            else None
        )

    def _record(self, job: str, fn: Callable[[db.Conn], dict[str, Any]]) -> dict[str, Any]:
        with self.pool.connection() as conn:
            conn.autocommit = True
            run_id = db.start_job(conn, job)
            try:
                detail = fn(conn)
            except Exception as exc:
                log.exception("job failed", extra={"job": job})
                db.finish_job(conn, run_id, False, {"error": str(exc)})
                return {"error": str(exc)}
            db.finish_job(conn, run_id, True, detail)
            return detail

    # Jobs

    def heartbeat(self) -> None:
        with self.pool.connection() as conn:
            conn.autocommit = True
            db.heartbeat(conn, VERSION)

    def bar_close(self, attempt: int = 0, symbols: list[str] | None = None) -> None:
        if self.oanda is None:
            log.warning("forex_bar_close skipped: OANDA_API_TOKEN not set")
            return
        oanda = self.oanda

        def work(conn: db.Conn) -> dict[str, Any]:
            insts = db.list_instruments(conn)
            if symbols is not None:
                insts = [i for i in insts if i.symbol in symbols]
            return forex_bar_close.run(conn, oanda, self.registry, datetime.now(UTC), insts)

        detail = self._record("forex_bar_close", work)
        stale = detail.get("stale") or []
        if stale and attempt < len(BAR_RETRIES):
            delay = BAR_RETRIES[attempt] - (BAR_RETRIES[attempt - 1] if attempt else 0)
            self.scheduler.add_job(
                self.bar_close,
                DateTrigger(datetime.now(UTC) + timedelta(seconds=delay)),
                kwargs={"attempt": attempt + 1, "symbols": stale},
                id=f"forex_bar_close_retry_{attempt + 1}",
                replace_existing=True,
            )
        elif stale:
            log.warning("no new completed bar", extra={"instruments": stale})

    def day_roll(self) -> None:
        if self.oanda is None:
            log.warning("forex_day_roll skipped: OANDA_API_TOKEN not set")
            return
        oanda = self.oanda
        self._record(
            "forex_day_roll",
            lambda conn: forex_day_roll.run(conn, oanda, self.registry, datetime.now(UTC)),
        )

    def stock_eod(self) -> None:
        if self.massive is None:
            log.warning("stock_eod skipped: MASSIVE_API_KEY not set")
            return
        massive = self.massive
        session = datetime.now(NEW_YORK).date()
        detail = self._record(
            "stock_eod", lambda conn: stock_eod.run(conn, massive, self.registry, session)
        )
        if detail.get("ready") is False:
            retry_at = datetime.now(UTC) + STOCK_RETRY
            if retry_at.astimezone(NEW_YORK).hour < STOCK_LAST_TRY_HOUR:
                self.scheduler.add_job(
                    self.stock_eod,
                    DateTrigger(retry_at),
                    id="stock_eod_retry",
                    replace_existing=True,
                )
            else:
                log.warning("stock bars missing by 23:00", extra={"session": str(session)})

    def ticker_refresh(self) -> None:
        if self.massive is None:
            return
        massive = self.massive

        def work(conn: db.Conn) -> dict[str, Any]:
            active, retired = refresh_universe(conn, massive)
            return {"active": active, "retired": retired}

        self._record("ticker_refresh", work)

    def retention(self) -> None:
        self._record("retention", db.apply_retention)


def build(
    pool: ConnectionPool, settings: Settings, scheduler: BaseScheduler | None = None
) -> Worker:
    sched = scheduler or BlockingScheduler(timezone=UTC, job_defaults=JOB_DEFAULTS)
    w = Worker(pool, settings, sched)
    ny = NEW_YORK
    sched.add_job(w.heartbeat, IntervalTrigger(seconds=60), id="heartbeat")
    # The job itself skips when forex is closed (weekends and holidays).
    sched.add_job(
        w.bar_close, CronTrigger(minute="0,15,30,45", second=5, timezone=UTC), id="forex_bar_close"
    )
    sched.add_job(
        w.day_roll,
        CronTrigger(day_of_week="sun,mon,tue,wed,thu,fri", hour=17, minute=1, timezone=ny),
        id="forex_day_roll",
    )
    sched.add_job(
        w.stock_eod,
        CronTrigger(day_of_week="mon-fri", hour=18, minute=30, timezone=ny),
        id="stock_eod",
    )
    sched.add_job(
        w.ticker_refresh,
        CronTrigger(day_of_week="sun", hour=12, minute=0, timezone=ny),
        id="ticker_refresh",
    )
    sched.add_job(w.retention, CronTrigger(hour=3, minute=0, timezone=UTC), id="retention")
    return w
