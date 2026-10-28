import os
from datetime import date, datetime

import pytest
from apscheduler.schedulers.background import BackgroundScheduler

from scanner import db, scheduler
from scanner.config import Settings
from scanner.data.base import DailyBar, ProviderAuthError
from scanner.time import NEW_YORK


def test_schedule_matches_spec_16() -> None:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    with db.make_pool(url, max_size=1) as pool:
        sched = BackgroundScheduler(job_defaults=scheduler.JOB_DEFAULTS)
        worker = scheduler.build(pool, Settings(database_url=url), sched)
        jobs = {j.id: str(j.trigger) for j in sched.get_jobs()}
        zones = {j.id: str(getattr(j.trigger, "timezone", "")) for j in sched.get_jobs()}
        assert set(jobs) == {"heartbeat", "forex_bar_close", "forex_day_roll", "stock_eod",
                             "stock_catch_up", "ticker_refresh", "retention", "new_pair_backfill",
                                "notify_outbox", "health_check"}  # fmt: skip
        assert (
            "minute='0,15,30,45'" in jobs["forex_bar_close"]
            and "second='5'" in jobs["forex_bar_close"]
        )
        assert "hour='17'" in jobs["forex_day_roll"]
        assert zones["forex_day_roll"] == zones["stock_eod"] == "America/New_York"
        assert zones["forex_bar_close"] == "UTC"
        assert "hour='18'" in jobs["stock_eod"] and "minute='30'" in jobs["stock_eod"]
        assert "hour='6'" in jobs["stock_catch_up"] and "minute='30'" in jobs["stock_catch_up"]
        assert zones["stock_catch_up"] == "America/New_York"
        # Without API keys the provider jobs skip instead of failing.
        assert worker.oanda is None and worker.massive is None
        worker.bar_close()
        worker.stock_eod()
        worker.stock_catch_up()
        worker.heartbeat()
        with pool.connection() as conn:
            row = conn.execute("SELECT version FROM worker_heartbeat").fetchone()
            assert row == (scheduler.VERSION,)
            conn.execute("UPDATE worker_heartbeat SET version = 'seed'")
            conn.commit()


def test_paused_forex_skips_forex_jobs_and_market_status() -> None:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    with db.make_pool(url, max_size=1) as pool:
        sched = BackgroundScheduler(job_defaults=scheduler.JOB_DEFAULTS)
        worker = scheduler.build(pool, Settings(database_url=url), sched)
        with pool.connection() as conn:
            before = conn.execute("SELECT forex_enabled FROM app_settings").fetchone()
            conn.execute("UPDATE app_settings SET forex_enabled = false")
            conn.commit()
        try:
            assert worker.forex_paused("forex_bar_close")
            worker.heartbeat()
            with pool.connection() as conn:
                assert conn.execute("SELECT market FROM worker_heartbeat").fetchone() == (None,)
                conn.execute("UPDATE app_settings SET forex_enabled = true")
                conn.commit()
            assert not worker.forex_paused("forex_bar_close")
            worker.heartbeat()
            with pool.connection() as conn:
                market = conn.execute("SELECT market FROM worker_heartbeat").fetchone()
                assert market is not None and market[0] is not None
        finally:
            with pool.connection() as conn:
                conn.execute(
                    "UPDATE app_settings SET forex_enabled = %s", (before[0] if before else True,)
                )
                conn.execute("UPDATE worker_heartbeat SET version = 'seed', market = NULL")
                conn.commit()


class _NoSameDay:
    """Massive's free plan: the same-day file is refused, earlier sessions are empty here."""

    def __init__(self) -> None:
        self.asked: list[date] = []

    def grouped_daily(self, session_date: date) -> list[DailyBar]:
        self.asked.append(session_date)
        if session_date == datetime.now(NEW_YORK).date():
            raise ProviderAuthError("massive returned 403")
        return []


def test_evening_403_defers_to_the_morning_catch_up() -> None:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    with db.make_pool(url, max_size=1) as pool:
        sched = BackgroundScheduler(job_defaults=scheduler.JOB_DEFAULTS)
        worker = scheduler.build(pool, Settings(database_url=url), sched)
        fake = _NoSameDay()
        worker.massive = fake  # type: ignore[assignment]
        with pool.connection() as conn:
            row = conn.execute("SELECT coalesce(max(id), 0) FROM job_runs").fetchone()
            first = row[0] if row else 0
        try:
            today = datetime.now(NEW_YORK).date()
            if today.weekday() < 5:
                worker.stock_eod()
                with pool.connection() as conn:
                    ok, detail = conn.execute(
                        "SELECT ok, detail FROM job_runs WHERE id > %s AND job = 'stock_eod' "
                        "ORDER BY id DESC LIMIT 1",
                        (first,),
                    ).fetchone() or (None, None)
                assert ok is True and detail["deferred"] is True
                assert sched.get_job("stock_eod_retry") is None  # no retries against a 403
            fake.asked.clear()
            worker.stock_catch_up()
            # The oldest missed session is tried first; it is empty here, so the run stops.
            assert len(fake.asked) == 1 and fake.asked[0] < today
        finally:
            with pool.connection() as conn:
                conn.execute("DELETE FROM job_runs WHERE id > %s", (first,))
                conn.commit()
