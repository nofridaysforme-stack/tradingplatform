"""Scanner entry point. The scheduler and jobs are added in later phases."""

import json
import logging
import os
import sys
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
                "level": record.levelname.lower(),
                "logger": record.name,
                "msg": record.getMessage(),
            }
        )


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(os.environ.get("LOG_LEVEL", "info").upper())


def main() -> None:
    configure_logging()
    logging.getLogger("scanner").info("scanner starting")


if __name__ == "__main__":
    main()
