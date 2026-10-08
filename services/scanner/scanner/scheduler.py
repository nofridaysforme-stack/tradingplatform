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
from scanner.jobs import backfill, forex_bar_close, forex_day_roll, stock_eod
from scanner.market_status import market_status
from scanner.notify import dispatcher, health, sources
from scanner.notify.channels import build_senders
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
        self.senders = build_senders(settings)
        self.base_url = settings.app_url.rstrip("/")
        self.ops_email = settings.ops_alert_email
        log.info("notification channels", extra={"channels": sorted(self.senders)})

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

    def forex_paused(self, job: str) -> bool:
        """True while the portal's forex switch is off; the forex jobs then do nothing."""
        with self.pool.connection() as conn:
            paused = not db.forex_enabled(conn)
        if paused:
            log.debug("forex paused, job skipped", extra={"job": job})
        return paused

    # Jobs

    def heartbeat(self) -> None:
        with self.pool.connection() as conn:
            conn.autocommit = True
            market: dict[str, Any] | None = None
            try:
                self.registry.refresh(conn)
                if not db.forex_enabled(conn):
                    # Forex is paused: no market status, so nothing reports pairs as stale.
                    db.heartbeat(conn, VERSION, None)
                    return
                status = market_status(
                    datetime.now(UTC),
                    self.registry.ruleset,
                    db.holidays(conn, "forex"),
                    db.last_m15_bars(conn),
                )
                market = status.model_dump(mode="json")
            except Exception:
                # The heartbeat itself must still be written; the portal shows the status
                # as unknown.
                log.exception("market status failed")
            db.heartbeat(conn, VERSION, market)

    def bar_close(self, attempt: int = 0, symbols: list[str] | None = None) -> None:
        if self.forex_paused("forex_bar_close"):
            return
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
        if self.forex_paused("forex_day_roll"):
            return
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
        if detail.get("ready") and "digest" in detail:
            self.stock_notifications(detail)
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

    def new_pair_backfill(self) -> None:
        """Backfill history for pairs added in Settings, so their levels exist before the
        next day roll."""
        if self.oanda is None or self.forex_paused("new_pair_backfill"):
            return
        oanda = self.oanda
        with self.pool.connection() as conn:
            conn.autocommit = True
            pending = db.instruments_without_history(conn)
            if not pending:
                return
            log.info("backfilling new pairs", extra={"pairs": [i.symbol for i in pending]})
            try:
                backfill.backfill_forex(conn, oanda, pending, datetime.now(UTC))
            except Exception:
                log.exception("new pair backfill failed")

    # Notifications (spec 11)

    def stock_notifications(self, detail: dict[str, Any]) -> None:
        """The evening digest and holding alerts from a finished stock screen."""
        now = datetime.now(UTC)
        session = str(detail["session"])
        with self.pool.connection() as conn:
            conn.autocommit = True
            try:
                if detail.get("digest"):
                    sources.dispatch_digest(
                        conn, detail["digest"], session, self.senders, now, self.base_url
                    )
                if detail.get("holdings"):
                    sources.dispatch_holdings(
                        conn, detail["holdings"], session, self.senders, now, self.base_url
                    )
            except Exception:
                log.exception("stock notifications failed")
        self.notify_outbox()

    def notify_outbox(self) -> None:
        """Every 10 seconds: new signals and updates, then every queued send that is due
        (first tries, retries, and test notifications queued by the portal)."""
        now = datetime.now(UTC)
        with self.pool.connection() as conn:
            conn.autocommit = True
            try:
                sources.dispatch_signal_events(conn, self.senders, now, self.base_url)
                counts = dispatcher.deliver_due(conn, self.senders, now, base_url=self.base_url)
                if counts:
                    log.info("notifications", extra=counts)
            except Exception:
                log.exception("notification outbox failed")

    def health_check(self) -> None:
        def work(conn: db.Conn) -> dict[str, Any]:
            return dict(
                health.run_health_check(
                    conn, self.senders, datetime.now(UTC), self.base_url, self.ops_email
                )
            )

        self._record("health_check", work)
        self.notify_outbox()

    def retention(self) -> None:
        self._record("retention", db.apply_retention)


def build(
    pool: ConnectionPool, settings: Settings, scheduler: BaseScheduler | None = None
) -> Worker:
    sched = scheduler or BlockingScheduler(timezone=UTC, job_defaults=JOB_DEFAULTS)
    w = Worker(pool, settings, sched)
    ny = NEW_YORK
    sched.add_job(
        w.heartbeat, IntervalTrigger(seconds=60), id="heartbeat", next_run_time=datetime.now(UTC)
    )
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
    sched.add_job(w.new_pair_backfill, IntervalTrigger(minutes=5), id="new_pair_backfill")
    sched.add_job(w.notify_outbox, IntervalTrigger(seconds=10), id="notify_outbox")
    sched.add_job(w.health_check, IntervalTrigger(minutes=5), id="health_check")
    return w
