import json
import os
from datetime import date

import psycopg
import pytest

from scanner import db
from scanner.jobs import levels as levels_job
from tests.test_db import _daily_fixture


def test_levels_command_prints_and_stores(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    monkeypatch.setenv("DATABASE_URL", url)
    # The command commits, so set up and clean up with a separate connection.
    with psycopg.connect(url, autocommit=True) as conn:
        eur = db.get_instrument(conn, "EUR/USD")
        db.upsert_candles(conn, eur.id, _daily_fixture())
    try:
        levels_job.main(["--day", "2026-09-30", "--instrument", "EUR/USD"])
        out = [
            json.loads(line)
            for line in capsys.readouterr().out.splitlines()
            if line.startswith("{")
        ]
        printed = [o for o in out if o.get("instrument") == "EUR/USD"]
        assert printed[0]["trading_day"] == "2026-09-30"
        assert printed[0]["fib_pivot"]["up"]["break"] == 1.0925
        with psycopg.connect(url) as conn:
            assert "daily" in db.get_levels(conn, eur.id, date(2026, 9, 30))
    finally:
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute("DELETE FROM levels WHERE instrument_id = %s", (eur.id,))
            conn.execute("DELETE FROM candles WHERE instrument_id = %s", (eur.id,))
            conn.execute("DELETE FROM job_runs")
