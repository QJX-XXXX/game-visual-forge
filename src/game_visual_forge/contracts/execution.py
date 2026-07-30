from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PlanStep:
    step_id: str
    action: str
    owner: str
    depends_on: tuple[str, ...]
    requires_confirmation: bool

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
        if int(value["schema_version"]) != 1:
            raise ValueError("unsupported ExecutionPlan schema_version")
        plan = cls(
            schema_version=1,
            plan_id=str(value["plan_id"]),
            asset_id=str(value["asset_id"]),
            source_preference=str(value["source_preference"]),
            dry_run=bool(value["dry_run"]),
            steps=tuple(
                PlanStep(
                    step_id=str(item["step_id"]),
                    action=str(item["action"]),
                    owner=str(item["owner"]),
                    depends_on=tuple(str(dep) for dep in item["depends_on"]),
                    requires_confirmation=bool(item["requires_confirmation"]),
                )
                for item in value["steps"]
            ),
        )
        plan.validate()
        return plan

    def validate(self) -> None:
        seen: set[str] = set()
        for step in self.steps:
            if step.step_id in seen:
                raise ValueError(f"duplicate step_id: {step.step_id}")
            if not set(step.depends_on).issubset(seen):
                raise ValueError(f"step dependencies must precede {step.step_id}")
            seen.add(step.step_id)
