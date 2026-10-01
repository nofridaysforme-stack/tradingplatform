from typing import Any
from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb

from scanner import db
from scanner.rules.registry import Registry, RuleSet, UnknownRuleError, load_ruleset
from scanner.rules.versions import RuleVersion

Conn = psycopg.Connection[Any]


def rule(key: str, params: dict[str, Any], schema: dict[str, Any], **kw: Any) -> RuleVersion:
    base: dict[str, Any] = {
        "key": key, "strategy": key.split(".", maxsplit=1)[0], "kind": "indicator", "name": key,
        "source": "test", "version": 1, "status": "approved", "enabled": True,
        "counts_toward_minimum": True, "description": "", "params_schema": schema,
        "params": params,
    }  # fmt: skip
    return RuleVersion(**{**base, **kw})


def test_resolution_order_override_then_version_then_default() -> None:
    eur = uuid4()
    schema = {"a": {"type": "pips", "default": 1}, "b": {"type": "pips", "default": 2},
              "c": {"type": "pips", "default": 3}}  # fmt: skip
    rs = RuleSet({"x.r": rule("x.r", {"b": 20}, schema)}, {("x.r", eur): {"c": 300}})
    assert rs.params("x.r") == {"a": 1, "b": 20, "c": 3}
    assert rs.params("x.r", eur) == {"a": 1, "b": 20, "c": 300}
    assert rs.params("x.r", uuid4()) == {"a": 1, "b": 20, "c": 3}


def test_version_set_and_lookups() -> None:
    rs = RuleSet({
        "x.b": rule("x.b", {}, {}, version=3),
        "x.a": rule("x.a", {}, {}, status="provisional", enabled=False),
        "y.a": rule("y.a", {}, {}),
    })  # fmt: skip
    assert rs.version_set(strategy="x") == {"x.a": 1, "x.b": 3}
    assert rs.version_set(["y.a"]) == {"y.a": 1}
    assert rs.provisional("x.a") and not rs.enabled("x.a") and not rs.enabled("nope")
    assert [r.key for r in rs.for_strategy("x", "indicator")] == ["x.b", "x.a"]
    with pytest.raises(UnknownRuleError):
        rs.rule("nope")


def test_load_from_database(conn: Conn) -> None:
    rs = load_ruleset(conn)
    assert rs.rule("three_eight.target").version == 2
    assert rs.params("three_eight.target")["reject_below_min"] is False
    assert rs.params("three_eight.cooldown") == {"bars": 4}
    counting = [r for r in rs.for_strategy("three_eight") if r.counts_toward_minimum]
    assert len(counting) == 8


def test_registry_reloads_when_revision_changes(conn: Conn) -> None:
    registry = Registry.load(conn)
    assert registry.refresh(conn) is False
    eur = db.get_instrument(conn, "EUR/USD")
    conn.execute(
        "INSERT INTO strategy_param_overrides (key, instrument_id, params) VALUES (%s, %s, %s)",
        ("three_eight.pdh", eur.id, Jsonb({"tolerance_pips": 7})),
    )
    conn.execute("UPDATE rule_config_revision SET revision = revision + 1")
    assert registry.refresh(conn) is True
    assert registry.ruleset.params("three_eight.pdh", eur.id)["tolerance_pips"] == 7
