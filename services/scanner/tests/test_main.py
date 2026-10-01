import json
import logging
import os

import pytest

from scanner import db
from scanner import main as main_module
from scanner.main import JsonFormatter


def test_json_formatter_outputs_valid_json_with_extras() -> None:
    record = logging.LogRecord("scanner", logging.INFO, __file__, 1, "hello", None, None)
    record.instrument = "EUR/USD"
    payload = json.loads(JsonFormatter().format(record))
    assert payload["msg"] == "hello"
    assert payload["level"] == "info"
    assert payload["instrument"] == "EUR/USD"
    assert payload["ts"].endswith("+00:00")


@pytest.fixture
def database_url(monkeypatch: pytest.MonkeyPatch) -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    monkeypatch.setenv("DATABASE_URL", url)
    return url


def _lines(capsys: pytest.CaptureFixture[str]) -> list[dict[str, object]]:
    return [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]


@pytest.mark.usefixtures("database_url")
def test_main_checks_schema(capsys: pytest.CaptureFixture[str]) -> None:
    main_module.main(start_scheduler=False)
    lines = _lines(capsys)
    assert lines[0]["msg"] == "scanner starting"
    assert lines[-1]["msg"] == "schema ok"


@pytest.mark.usefixtures("database_url")
def test_main_exits_when_schema_is_behind(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def behind(conn: db.Conn, expected: str = "") -> str:
        raise db.SchemaBehindError("database schema is at 1, scanner expects 2")

    monkeypatch.setattr(db, "check_schema", behind)
    with pytest.raises(SystemExit) as exc:
        main_module.main(start_scheduler=False)
    assert exc.value.code == 1
    assert _lines(capsys)[-1]["msg"] == "schema check failed"
