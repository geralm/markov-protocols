"""A state whose ``requires`` are produced by the host running a side effect.

The machine never runs the action: it surfaces ``payload`` (with ``Ref``s resolved)
as a ``directive`` for the host, then waits for the host to write the required
result field(s) back. It consumes its ``payload`` refs and produces its ``requires``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, cast

from pydantic import Field, field_validator

from ...references import normalize_refs, referenced_fields, resolve
from ..blocker import Blocker, BlockReason
from ..state import Directive, Requirement, State


class ActionExecuteState(State):
    """Completes when the host writes the action's result(s) to the Blackboard."""

    type: Literal["ACTION_EXECUTE"] = "ACTION_EXECUTE"
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("payload", mode="after")
    @classmethod
    def _normalize_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        return normalize_refs(value)

    def depends_on(self) -> set[str]:
        return referenced_fields(self.payload)

    def produces(self) -> set[str]:
        return {r.field for r in self.requires}

    def directive(self, data: Mapping[str, Any]) -> Directive:
        resolved = resolve(self.payload, data)
        if resolved.is_success:
            # Resolving a dict payload always yields a dict on success.
            payload = cast(dict[str, Any], resolved.value)
            return Directive(kind="action", ready=True, payload=payload)
        return Directive(kind="action", ready=False, missing=resolved.error_details or [])

    def _absent_field_blocker(self, requirement: Requirement) -> Blocker:
        return Blocker(
            reason=BlockReason.AWAITING_RESULT,
            field=requirement.field,
            detail=f"waiting for the result '{requirement.field}' of '{self.title}'",
        )
