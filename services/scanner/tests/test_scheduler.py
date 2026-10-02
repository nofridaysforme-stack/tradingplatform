import os

import pytest
from apscheduler.schedulers.background import BackgroundScheduler

from scanner import db, scheduler
from scanner.config import Settings


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
                             "ticker_refresh", "retention", "new_pair_backfill"}  # fmt: skip
        assert (
            "minute='0,15,30,45'" in jobs["forex_bar_close"]
            and "second='5'" in jobs["forex_bar_close"]
        )
        assert "hour='17'" in jobs["forex_day_roll"]
        assert zones["forex_day_roll"] == zones["stock_eod"] == "America/New_York"
        assert zones["forex_bar_close"] == "UTC"
        assert "hour='18'" in jobs["stock_eod"] and "minute='30'" in jobs["stock_eod"]
        # Without API keys the provider jobs skip instead of failing.
        assert worker.oanda is None and worker.massive is None
        worker.bar_close()
        worker.stock_eod()
        worker.heartbeat()
        with pool.connection() as conn:
            row = conn.execute("SELECT version FROM worker_heartbeat").fetchone()
            assert row == (scheduler.VERSION,)
            conn.execute("UPDATE worker_heartbeat SET version = 'seed'")
            conn.commit()
