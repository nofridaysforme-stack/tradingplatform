"""Loads every current rule version and per-instrument override, and reloads them when an
admin change bumps rule_config_revision. Strategies read parameters only through a RuleSet.

Resolution order for a parameter (spec 05): instrument override, then the rule version's
value, then the parameter default.
"""

import logging
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from scanner import db
from scanner.rules.versions import RuleVersion

log = logging.getLogger(__name__)


class UnknownRuleError(KeyError):
    pass


class RuleSet:
    """An immutable snapshot of the rules. Pure: tests and the backtester build one directly."""

    def __init__(
        self,
        rules: dict[str, RuleVersion],
        overrides: dict[tuple[str, UUID], dict[str, Any]] | None = None,
        revision: int = 0,
    ) -> None:
        self._rules = rules
        self._overrides = overrides or {}
        self.revision = revision

    def rule(self, key: str) -> RuleVersion:
        try:
            return self._rules[key]
        except KeyError as exc:
            raise UnknownRuleError(key) from exc

    def has(self, key: str) -> bool:
        return key in self._rules

    def enabled(self, key: str) -> bool:
        return self.has(key) and self._rules[key].enabled

    def provisional(self, key: str) -> bool:
        return self.rule(key).provisional

    def params(self, key: str, instrument_id: UUID | None = None) -> dict[str, Any]:
        rule = self.rule(key)
        resolved = {**rule.defaults(), **rule.params}
        if instrument_id is not None:
            resolved.update(self._overrides.get((key, instrument_id), {}))
        return resolved

    def for_strategy(self, strategy: str, kind: str | None = None) -> list[RuleVersion]:
        return [
            r
            for r in self._rules.values()
            if r.strategy == strategy and (kind is None or r.kind == kind)
        ]

    def version_set(
        self, keys: list[str] | None = None, strategy: str | None = None
    ) -> dict[str, int]:
        """The exact rule versions behind a signal (stored on every signal)."""
        chosen = (
            [self.rule(k) for k in keys]
            if keys is not None
            else [r for r in self._rules.values() if strategy is None or r.strategy == strategy]
        )
        return {r.key: r.version for r in sorted(chosen, key=lambda r: r.key)}


def derive(
    ruleset: RuleSet,
    params: dict[str, dict[str, Any]] | None = None,
    disabled: set[str] | None = None,
) -> RuleSet:
    """A copy with some parameters changed or rules switched off. Used by the backtester's
    sweeps; never written back. Version numbers stay as loaded, so reports record which
    versions were varied and how."""
    rules = {}
    for key in ruleset._rules:
        rule = ruleset.rule(key)
        update: dict[str, Any] = {}
        if params and key in params:
            update["params"] = {**rule.params, **params[key]}
        if disabled and key in disabled:
            update["enabled"] = False
        rules[key] = rule.model_copy(update=update) if update else rule
    unknown = (set(params or {}) | set(disabled or set())) - set(rules)
    if unknown:
        raise UnknownRuleError(", ".join(sorted(unknown)))
    return RuleSet(rules, ruleset._overrides, ruleset.revision)


def load_ruleset(conn: db.Conn) -> RuleSet:
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            "SELECT d.key, d.strategy::text AS strategy, d.kind::text AS kind, d.name, d.source, "
            "v.version, v.status::text AS status, v.enabled, v.counts_toward_minimum, "
            "v.description, v.params_schema, v.params "
            "FROM rule_definitions d "
            "JOIN rule_versions v ON v.key = d.key AND v.version = d.current_version"
        ).fetchall()
        overrides = {
            (r["key"], r["instrument_id"]): r["params"]
            for r in cur.execute("SELECT key, instrument_id, params FROM strategy_param_overrides")
        }
    revision = current_revision(conn)
    return RuleSet({r["key"]: RuleVersion(**r) for r in rows}, overrides, revision)


def current_revision(conn: db.Conn) -> int:
    row = conn.execute("SELECT revision FROM rule_config_revision").fetchone()
    return int(row[0]) if row else 0


class Registry:
    """Holds the current RuleSet for the live worker. Call refresh() before each bar."""

    def __init__(self, ruleset: RuleSet) -> None:
        self.ruleset = ruleset

    @classmethod
    def load(cls, conn: db.Conn) -> "Registry":
        return cls(load_ruleset(conn))

    def refresh(self, conn: db.Conn) -> bool:
        """Reload when the revision counter changed. Returns True when it reloaded."""
        revision = current_revision(conn)
        if revision == self.ruleset.revision:
            return False
        self.ruleset = load_ruleset(conn)
        log.info("rules reloaded", extra={"revision": self.ruleset.revision})
        return True
