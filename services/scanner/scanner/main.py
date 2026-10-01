"""Scanner entry point. Checks the schema, then (from Phase 2) starts the scheduler."""

import json
import logging
import os
import sys
from datetime import UTC, datetime
from typing import Any

from scanner import db
from scanner.config import Settings

# Attributes every LogRecord has; anything else was passed with extra= and is logged.
_STANDARD_ATTRS = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {
    "message",
    "asctime",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in vars(record).items():
            if key not in _STANDARD_ATTRS:
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(os.environ.get("LOG_LEVEL", "info").upper())
    # httpx logs full request URLs at info level; keep them out of the logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)


def main() -> None:
    configure_logging()
    log = logging.getLogger("scanner")
    log.info("scanner starting")
    settings = Settings()  # values come from the environment
    with db.make_pool(settings.database_url, max_size=1) as pool, pool.connection() as conn:
        try:
            version = db.check_schema(conn)
        except db.SchemaBehindError as exc:
            log.error("schema check failed", extra={"reason": str(exc)})
            raise SystemExit(1) from exc
    log.info("schema ok", extra={"schema_version": version})


if __name__ == "__main__":
    main()
