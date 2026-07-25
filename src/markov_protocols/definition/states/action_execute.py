"""A state that represents the host running an action and reporting its result."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, cast

from pydantic import Field, field_validator

from ...conditions.models import Condition, Exists
from ...references import normalize_refs, referenced_fields, resolve
from ..state import Directive, State


class ActionExecuteState(State):
    """Completes when the host writes the action's outcome to ``result_field``.

    The machine never runs the action. It surfaces the ``payload`` (with any
    ``Ref`` resolved) for the host to execute, then waits for the result to land.
    Because the payload *consumes* the fields it references, changing any of them
    later reopens this state.
    """

    type: Literal["ACTION_EXECUTE"] = "ACTION_EXECUTE"
    payload: dict[str, Any] = Field(default_factory=dict)
    result_field: str

    @field_validator("payload", mode="after")
    @classmethod
    def _normalize_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        return normalize_refs(value)

    def completion_condition(self) -> Condition:
        return Exists(field=self.result_field)

    def depends_on(self) -> set[str]:
        return referenced_fields(self.payload)

    def produces(self) -> set[str]:
        return {self.result_field}

    def directive(self, data: Mapping[str, Any]) -> Directive:
        resolved = resolve(self.payload, data)
        if resolved.is_success:
            # Resolving a dict payload always yields a dict on success.
            payload = cast(dict[str, Any], resolved.value)
            return Directive(kind="action", ready=True, payload=payload)
        return Directive(kind="action", ready=False, missing=resolved.error_details or [])
