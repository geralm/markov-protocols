"""A state whose ``requires`` are produced by a human being notified.

The machine surfaces ``notify`` (with ``Ref``s resolved) as a ``directive`` so the
host can reach the human, then waits for the required resolution field(s). It
consumes its ``notify`` refs and produces its ``requires``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, cast

from pydantic import Field, field_validator

from ...references import normalize_refs, referenced_fields, resolve
from ..blocker import Blocker, BlockReason
from ..state import Directive, Requirement, State


class HumanHandoffState(State):
    """Completes when a human writes the resolution field(s) to the Blackboard."""

    type: Literal["HUMAN_HANDOFF"] = "HUMAN_HANDOFF"
    notify: dict[str, Any] = Field(default_factory=dict)

    @field_validator("notify", mode="after")
    @classmethod
    def _normalize_notify(cls, value: dict[str, Any]) -> dict[str, Any]:
        return normalize_refs(value)

    def depends_on(self) -> set[str]:
        return referenced_fields(self.notify)

    def produces(self) -> set[str]:
        return {r.field for r in self.requires}

    def directive(self, data: Mapping[str, Any]) -> Directive:
        resolved = resolve(self.notify, data)
        if resolved.is_success:
            # Resolving a dict payload always yields a dict on success.
            payload = cast(dict[str, Any], resolved.value)
            return Directive(kind="handoff", ready=True, payload=payload)
        return Directive(kind="handoff", ready=False, missing=resolved.error_details or [])

    def _absent_field_blocker(self, requirement: Requirement) -> Blocker:
        return Blocker(
            reason=BlockReason.AWAITING_HUMAN,
            field=requirement.field,
            detail=f"waiting for a human to provide '{requirement.field}' in '{self.title}'",
        )
