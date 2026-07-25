"""A state that waits for a human to act before the workflow continues."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, cast

from pydantic import Field, field_validator

from ...conditions.models import Condition, Exists
from ...references import normalize_refs, referenced_fields, resolve
from ..blocker import Blocker, BlockReason
from ..state import Directive, State, field_present


class HumanHandoffState(State):
    """Completes when a resolution signal is written to ``resolution_field``.

    The machine surfaces the ``notify`` payload (with any ``Ref`` resolved) so the
    host can reach the human; it does not send anything itself.
    """

    type: Literal["HUMAN_HANDOFF"] = "HUMAN_HANDOFF"
    notify: dict[str, Any] = Field(default_factory=dict)
    resolution_field: str

    @field_validator("notify", mode="after")
    @classmethod
    def _normalize_notify(cls, value: dict[str, Any]) -> dict[str, Any]:
        return normalize_refs(value)

    def completion_condition(self) -> Condition:
        return Exists(field=self.resolution_field)

    def depends_on(self) -> set[str]:
        return referenced_fields(self.notify)

    def produces(self) -> set[str]:
        return {self.resolution_field}

    def directive(self, data: Mapping[str, Any]) -> Directive:
        resolved = resolve(self.notify, data)
        if resolved.is_success:
            # Resolving a dict payload always yields a dict on success.
            payload = cast(dict[str, Any], resolved.value)
            return Directive(kind="handoff", ready=True, payload=payload)
        return Directive(kind="handoff", ready=False, missing=resolved.error_details or [])

    def blockers(self, data: Mapping[str, Any]) -> list[Blocker]:
        unresolved = sorted(
            f for f in referenced_fields(self.notify) if not field_present(data, f)
        )
        if unresolved:
            return [
                Blocker(
                    reason=BlockReason.MISSING,
                    field=f,
                    detail=f"'{f}' is needed to notify for '{self.title}'",
                )
                for f in unresolved
            ]
        if not field_present(data, self.resolution_field):
            return [
                Blocker(
                    reason=BlockReason.AWAITING_HUMAN,
                    field=self.resolution_field,
                    detail=f"waiting for a human to resolve '{self.title}'",
                )
            ]
        return []

    def to_llm_extended(self) -> str:
        return f"Step: {self.title} (handoff)\n- awaiting resolution in '{self.resolution_field}'"
