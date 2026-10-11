from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _require_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")
    return value


def _require_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{field_name} must be a boolean")
    return value


def _require_schema_version(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("schema_version must be an integer")
    if value != 1:
        raise ValueError("schema_version must be 1")
    return value


def _require_string_sequence(value: Any, field_name: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise TypeError(f"{field_name} must be a list of strings")
    return tuple(_require_string(item, field_name) for item in value)


def _require_step_sequence(value: Any) -> tuple["PlanStep", ...]:
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise TypeError("steps must be a list of PlanStep objects")
    steps = tuple(value)
    for step in steps:
        if not isinstance(step, PlanStep):
            raise TypeError("steps must contain PlanStep objects")
    return steps


def _require_json_object(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{field_name} must be a JSON object")
    return value


def _require_json_string_sequence(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise TypeError(f"{field_name} must be a JSON array")
    return _require_string_sequence(value, field_name)


@dataclass(frozen=True)
class PlanStep:
    step_id: str
    action: str
    owner: str
    depends_on: tuple[str, ...]
    requires_confirmation: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "step_id", _require_string(self.step_id, "step_id"))
        object.__setattr__(self, "action", _require_string(self.action, "action"))
        object.__setattr__(self, "owner", _require_string(self.owner, "owner"))
        object.__setattr__(
            self,
            "depends_on",
            _require_string_sequence(self.depends_on, "depends_on"),
        )
        object.__setattr__(
            self,
            "requires_confirmation",
            _require_bool(self.requires_confirmation, "requires_confirmation"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "action": self.action,
            "owner": self.owner,
            "depends_on": list(self.depends_on),
            "requires_confirmation": self.requires_confirmation,
        }


@dataclass(frozen=True)
class ExecutionPlan:
    schema_version: int
    plan_id: str
    asset_id: str
    source_preference: str
    dry_run: bool
    steps: tuple[PlanStep, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "schema_version",
            _require_schema_version(self.schema_version),
        )
        object.__setattr__(self, "plan_id", _require_string(self.plan_id, "plan_id"))
        object.__setattr__(self, "asset_id", _require_string(self.asset_id, "asset_id"))
        object.__setattr__(
            self,
            "source_preference",
            _require_string(self.source_preference, "source_preference"),
        )
        object.__setattr__(self, "dry_run", _require_bool(self.dry_run, "dry_run"))
        object.__setattr__(self, "steps", _require_step_sequence(self.steps))
        self.validate()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "plan_id": self.plan_id,
            "asset_id": self.asset_id,
            "source_preference": self.source_preference,
            "dry_run": self.dry_run,
            "steps": [step.to_dict() for step in self.steps],
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ExecutionPlan":
        if not isinstance(value, dict):
            raise TypeError("ExecutionPlan payload must be an object")
        steps = value["steps"]
        if not isinstance(steps, list):
            raise TypeError("steps must be a JSON array")
        return cls(
            schema_version=_require_schema_version(value["schema_version"]),
            plan_id=_require_string(value["plan_id"], "plan_id"),
            asset_id=_require_string(value["asset_id"], "asset_id"),
            source_preference=_require_string(
                value["source_preference"],
                "source_preference",
            ),
            dry_run=_require_bool(value["dry_run"], "dry_run"),
            steps=tuple(
                PlanStep(
                    step_id=_require_string(step["step_id"], "step_id"),
                    action=_require_string(step["action"], "action"),
                    owner=_require_string(step["owner"], "owner"),
                    depends_on=_require_json_string_sequence(
                        step["depends_on"],
                        "depends_on",
                    ),
                    requires_confirmation=_require_bool(
                        step["requires_confirmation"],
                        "requires_confirmation",
                    ),
                )
                for step in (
                    _require_json_object(item, "steps[]")
                    for item in steps
                )
            ),
        )

    def validate(self) -> None:
        seen: set[str] = set()
        for step in self.steps:
            if step.step_id in seen:
                raise ValueError(f"duplicate step_id: {step.step_id}")
            if not set(step.depends_on).issubset(seen):
                raise ValueError(f"step dependencies must precede {step.step_id}")
            seen.add(step.step_id)
