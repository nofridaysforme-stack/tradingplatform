import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import psycopg
import pytest

if TYPE_CHECKING:
    from scanner.rules.registry import RuleSet

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


def ruleset_from_snapshot() -> "RuleSet":
    from scanner.rules.registry import RuleSet  # noqa: PLC0415
    from scanner.rules.versions import RuleVersion  # noqa: PLC0415

    data = load_fixture("rules_snapshot.json")["rules"]
    return RuleSet({k: RuleVersion(**v) for k, v in data.items()})
