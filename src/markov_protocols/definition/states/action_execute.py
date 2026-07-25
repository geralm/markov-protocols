"""A state that represents the host running an action and reporting its result."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, cast

from pydantic import Field, field_validator

from ...conditions.models import Condition, Exists
from ...references import normalize_refs, referenced_fields, resolve
from ..blocker import Blocker, BlockReason
from ..state import Directive, State, field_present


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

    def blockers(self, data: Mapping[str, Any]) -> list[Blocker]:
        # Can't even run the action until its payload references are available.
        unresolved = sorted(
            f for f in referenced_fields(self.payload) if not field_present(data, f)
        )
        if unresolved:
            return [
                Blocker(
                    reason=BlockReason.MISSING,
                    field=f,
                    detail=f"'{f}' is needed to run '{self.title}'",
                )
                for f in unresolved
            ]
        # Payload is ready — now waiting for the host to run it and report back.
        if not field_present(data, self.result_field):
            return [
                Blocker(
                    reason=BlockReason.AWAITING_RESULT,
                    field=self.result_field,
                    detail=f"waiting for the result of '{self.title}'",
                )
            ]
        return []

    def to_llm_extended(self) -> str:
        return f"Step: {self.title} (action)\n- awaiting result in '{self.result_field}'"
