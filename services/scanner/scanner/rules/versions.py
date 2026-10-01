"""Rule versions as loaded from rule_definitions and rule_versions."""

from typing import Any, Literal

from pydantic import BaseModel

RuleKind = Literal["indicator", "gate", "plan", "filter", "lifecycle"]
RuleStatus = Literal["approved", "provisional"]


class RuleVersion(BaseModel):
    key: str
    strategy: str
    kind: RuleKind
    name: str
    source: str
    version: int
    status: RuleStatus
    enabled: bool
    counts_toward_minimum: bool
    description: str
    params_schema: dict[str, Any]
    params: dict[str, Any]

    @property
    def provisional(self) -> bool:
        return self.status == "provisional"

    def defaults(self) -> dict[str, Any]:
        return {name: spec.get("default") for name, spec in self.params_schema.items()}
