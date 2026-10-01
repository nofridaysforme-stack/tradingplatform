import json
import logging

import pytest

from scanner.main import JsonFormatter, main


def test_json_formatter_outputs_valid_json() -> None:
    record = logging.LogRecord("scanner", logging.INFO, __file__, 1, "hello", None, None)
    payload = json.loads(JsonFormatter().format(record))
    assert payload["msg"] == "hello"
    assert payload["level"] == "info"
    assert payload["ts"].endswith("+00:00")


def test_main_logs_start(capsys: pytest.CaptureFixture[str]) -> None:
    main()
    line = capsys.readouterr().out.strip().splitlines()[-1]
    assert json.loads(line)["msg"] == "scanner starting"
