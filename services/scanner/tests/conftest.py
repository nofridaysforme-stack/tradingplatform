import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def conn() -> Iterator[psycopg.Connection[Any]]:
    """A connection to a migrated database; everything a test writes is rolled back.

    Set TEST_DATABASE_URL to run database tests (CI does). They are skipped otherwise.
    """
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    with psycopg.connect(url) as c, c.transaction(force_rollback=True):
        yield c
