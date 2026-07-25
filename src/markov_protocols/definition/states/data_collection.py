"""A state that completes once the user has provided the required data."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import Field

from ...conditions.evaluate import evaluate
from ...conditions.models import Condition, Regex
from ..blocker import Blocker, BlockReason
from ..state import (
    Option,
    Requirement,
    State,
    all_of,
    field_present,
    requirement_condition,
    requirement_constraints,
)


class DataCollectionState(State):
    """Completes when every requirement is satisfied on the Blackboard.

    The data is produced by the host's LLM extracting it from the conversation;
    this state only declares *what* is needed, never *how* to obtain it.
    """

    type: Literal["DATA_COLLECTION"] = "DATA_COLLECTION"
    requires: list[Requirement] = Field(min_length=1)

    def completion_condition(self) -> Condition:
        return all_of([requirement_condition(r) for r in self.requires])

    def depends_on(self) -> set[str]:
        return {r.field for r in self.requires}

    def blockers(self, data: Mapping[str, Any]) -> list[Blocker]:
        result: list[Blocker] = []
        for req in self.requires:
            if not field_present(data, req.field):
                result.append(
                    Blocker(reason=BlockReason.MISSING, field=req.field, detail=_missing(req))
                )
                continue
            constraints = requirement_constraints(req)
            if constraints and not evaluate(all_of(constraints), data):
                detail = _invalid(req, data[req.field])
                result.append(Blocker(reason=BlockReason.INVALID, field=req.field, detail=detail))
        return result

    def field_options(self) -> dict[str, dict[str, Any]]:
        """What the agent can present per field: description, options, pattern."""
        result: dict[str, dict[str, Any]] = {}
        for req in self.requires:
            info: dict[str, Any] = {}
            if req.description:
                info["description"] = req.description
            if req.options:
                info["options"] = [
                    {"value": o.value, "description": o.description} for o in req.options
                ]
            if isinstance(req.condition, Regex):
                info["pattern"] = req.condition.value
            result[req.field] = info
        return result

    def to_llm_extended(self) -> str:
        lines = [f"Step: {self.title}"]
        for req in self.requires:
            line = f"- {req.field}"
            if req.description:
                line += f": {req.description}"
            if req.options:
                line += f" (one of: {', '.join(_option_text(o) for o in req.options)})"
            lines.append(line)
        return "\n".join(lines)


def _option_text(option: Option) -> str:
    return f"{option.value} ({option.description})" if option.description else str(option.value)


def _missing(req: Requirement) -> str:
    detail = f"'{req.field}' is required"
    return f"{detail} — {req.description}" if req.description else detail


def _invalid(req: Requirement, value: Any) -> str:
    if req.options:
        allowed = ", ".join(_option_text(o) for o in req.options)
        return f"'{req.field}' is invalid: {value!r} is not allowed; choose one of: {allowed}"
    if isinstance(req.condition, Regex):
        return f"'{req.field}' is invalid: {value!r} does not match the required format"
    return f"'{req.field}' is invalid: {value!r}"
