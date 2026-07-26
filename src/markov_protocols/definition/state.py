"""The ``State`` interface — the extension seam of the whole engine.

Every step declares ``requires``: the fields that must be present (and valid) for
it to advance. That single, uniform declaration drives the shared logic on the
base class — completion, blockers, the Pydantic schema, field options, rendering.

A concrete state type only fills in what makes it distinct:

* ``depends_on()`` — the fields it *consumes* (so a change reopens it).
* ``produces()``   — the fields it *outputs* (cleared on reopen so it re-runs).
* ``directive()``  — the side effect the host must run while it is active.
* ``_absent_field_blocker()`` — why a required field is absent (missing vs awaiting).

So the three built-ins differ only in "do I have a side effect" and "do I produce
my own requires (host/human) or receive them (user)".
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Literal, cast

from pydantic import BaseModel, Field, create_model

from ..base import StrictModel
from ..conditions.evaluate import evaluate
from ..conditions.models import All, Condition, Exists, In, Regex
from ..renderable import Renderable
from ..slug import slugify
from .blocker import Blocker, BlockReason
from .metadata import StateMetadata


class Status(StrEnum):
    """A state's lifecycle within one running session."""

    PENDING = "PENDING"  # not yet reached
    ACTIVE = "ACTIVE"  # the current step
    COMPLETED = "COMPLETED"  # its completion condition held
    REOPENED = "REOPENED"  # was completed, then data it depends on changed


class ValueType(StrEnum):
    """The type of a field's value — used to build the Pydantic schema."""

    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"


_PY_TYPES: dict[ValueType, Any] = {
    ValueType.STRING: str,
    ValueType.INTEGER: int,
    ValueType.NUMBER: float,
    ValueType.BOOLEAN: bool,
    ValueType.ARRAY: list,
}


class Directive(StrictModel, Renderable):
    """The host-actionable instruction a state surfaces while it is active.

    The machine never acts; it hands the host a fully-resolved ``payload`` to
    execute. ``ready`` is false when a referenced field is still missing, and
    ``missing`` names those fields — so a side effect can't fire half-blank.
    """

    kind: str
    ready: bool
    payload: dict[str, Any] = Field(default_factory=dict)
    missing: list[str] = Field(default_factory=list)

    def to_llm_extended(self) -> str:
        if self.ready:
            return f"Ready to run '{self.kind}'."
        if self.missing:
            return f"Cannot run '{self.kind}' yet — missing: {', '.join(self.missing)}."
        return f"Action '{self.kind}' is not ready."


class Option(StrictModel):
    """An allowed value for a field, with an optional description for the agent."""

    value: Any
    description: str | None = None


class Requirement(StrictModel):
    """A field a state expects.

    ``required`` (default true) decides whether it *gates* completion — an optional
    requirement is collected if it appears but never blocks. ``type`` drives the
    Pydantic schema; ``options`` fixes the allowed values (and auto-enforces them);
    ``condition`` adds any further rule; ``description`` explains it to the agent.
    """

    field: str
    description: str | None = None
    type: ValueType = ValueType.STRING
    required: bool = True
    options: list[Option] = Field(default_factory=list)
    condition: Condition | None = None


# --- helpers used by the base State ------------------------------------------


def field_present(data: Mapping[str, Any], field: str) -> bool:
    """Whether a field is present and non-null on the data."""
    return evaluate(Exists(field=field), data)


def all_of(conditions: list[Condition]) -> Condition:
    """Combine conditions with AND. A lone condition is returned unwrapped; an
    empty list is vacuously true (used when every requirement is optional)."""
    if len(conditions) == 1:
        return conditions[0]
    return All(of=conditions)


def requirement_constraints(requirement: Requirement) -> list[Condition]:
    """The value rules on a requirement, excluding mere existence."""
    parts: list[Condition] = []
    if requirement.options:
        parts.append(In(field=requirement.field, value=[o.value for o in requirement.options]))
    if requirement.condition is not None:
        parts.append(requirement.condition)
    return parts


def requirement_condition(requirement: Requirement) -> Condition:
    """A requirement holds when its field exists and satisfies its value rules."""
    return all_of([Exists(field=requirement.field), *requirement_constraints(requirement)])


def _option_text(option: Option) -> str:
    return f"{option.value} ({option.description})" if option.description else str(option.value)


def _missing_detail(requirement: Requirement) -> str:
    detail = f"'{requirement.field}' is required"
    return f"{detail} — {requirement.description}" if requirement.description else detail


def _invalid_detail(requirement: Requirement, value: Any) -> str:
    if requirement.options:
        allowed = ", ".join(_option_text(o) for o in requirement.options)
        return (
            f"'{requirement.field}' is invalid: {value!r} is not allowed; "
            f"choose one of: {allowed}"
        )
    if isinstance(requirement.condition, Regex):
        return f"'{requirement.field}' is invalid: {value!r} does not match the required format"
    return f"'{requirement.field}' is invalid: {value!r}"


def _schema_field(requirement: Requirement) -> tuple[Any, Any]:
    """Build a ``(type, FieldInfo)`` pair for one requirement in a Pydantic model."""
    if requirement.options:
        annotation: Any = Literal[tuple(o.value for o in requirement.options)]
    else:
        annotation = _PY_TYPES[requirement.type]

    kwargs: dict[str, Any] = {}
    if requirement.description:
        kwargs["description"] = requirement.description
    if (
        not requirement.options
        and requirement.type is ValueType.STRING
        and isinstance(requirement.condition, Regex)
    ):
        kwargs["pattern"] = requirement.condition.value

    if requirement.required:
        return (annotation, Field(**kwargs))
    return (annotation | None, Field(default=None, **kwargs))


def _model_name(title: str) -> str:
    parts = [p for p in slugify(title).split("-") if p]
    return "".join(p.capitalize() for p in parts) + "Inputs" if parts else "Inputs"


class State(StrictModel, Renderable, ABC):
    """A single step. ``id`` is derived from ``title`` and is never stored."""

    title: str
    metadata: StateMetadata = StateMetadata()
    requires: list[Requirement] = Field(min_length=1)

    @property
    def id(self) -> str:
        """The deterministic identifier: the slug of the title."""
        return slugify(self.title)

    # --- shared logic, driven entirely by ``requires`` -----------------

    def completion_condition(self) -> Condition:
        """True when every *required* requirement holds (optional ones don't gate)."""
        return all_of([requirement_condition(r) for r in self.requires if r.required])

    def expected_fields(self) -> list[Requirement]:
        """Every field this state expects — required and optional."""
        return list(self.requires)

    def to_pydantic_model(self) -> type[BaseModel]:
        """A Pydantic model of the expected fields — for LLM structured output and
        for validating the extracted result before it reaches the Blackboard."""
        fields: dict[str, Any] = {r.field: _schema_field(r) for r in self.requires}
        model = create_model(_model_name(self.title), **fields)
        return cast(type[BaseModel], model)

    def field_options(self) -> dict[str, dict[str, Any]]:
        """What the agent can present per field: required, type, description, options, pattern."""
        result: dict[str, dict[str, Any]] = {}
        for req in self.requires:
            info: dict[str, Any] = {"required": req.required, "type": req.type.value}
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

    def blockers(self, data: Mapping[str, Any]) -> list[Blocker]:
        """Why this state has not completed. Optional requirements never block."""
        result: list[Blocker] = []
        for req in self.requires:
            if not req.required:
                continue
            if not field_present(data, req.field):
                result.append(self._absent_field_blocker(req))
                continue
            constraints = requirement_constraints(req)
            if constraints and not evaluate(all_of(constraints), data):
                detail = _invalid_detail(req, data[req.field])
                result.append(Blocker(reason=BlockReason.INVALID, field=req.field, detail=detail))
        return result

    def to_llm_extended(self) -> str:
        lines = [f"Step: {self.title}"]
        for req in self.requires:
            line = f"- {req.field}"
            if not req.required:
                line += " (optional)"
            if req.description:
                line += f": {req.description}"
            if req.options:
                line += f" (one of: {', '.join(_option_text(o) for o in req.options)})"
            lines.append(line)
        return "\n".join(lines)

    # --- per-type hooks ------------------------------------------------

    @abstractmethod
    def depends_on(self) -> set[str]:
        """Blackboard fields this state consumes; a change to any of them reopens it."""

    def produces(self) -> set[str]:
        """Fields this state outputs when it completes (cleared on reopen so it re-runs).

        Empty by default (data collection — the user supplies the data). Action and
        handoff states produce their ``requires``.
        """
        return set()

    def directive(self, data: Mapping[str, Any]) -> Directive | None:
        """The side effect the host must run while this state is active. ``None`` by
        default; action/handoff states override it."""
        return None

    def _absent_field_blocker(self, requirement: Requirement) -> Blocker:
        """The blocker for a required field that is absent. Default: the user hasn't
        supplied it yet (``MISSING``); action/handoff override to an ``AWAITING_*``."""
        detail = _missing_detail(requirement)
        return Blocker(reason=BlockReason.MISSING, field=requirement.field, detail=detail)
