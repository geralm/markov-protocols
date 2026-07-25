"""Events: the append-only record of everything that happens in a session.

Each event is a typed, serializable fact tagged by ``kind``. The order of the
history list *is* the sequence — we deliberately record no wall-clock timestamp,
so the same inputs always produce the same history (determinism and replay). A
host that needs timestamps records them alongside.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field

from ..base import StrictModel


class ValueSet(StrictModel):
    """A field was written for the first time."""

    kind: Literal["value_set"] = "value_set"
    field: str
    value: Any


class ValueChanged(StrictModel):
    """A field that already had a value was overwritten with a different one."""

    kind: Literal["value_changed"] = "value_changed"
    field: str
    old: Any
    new: Any


class StateCompleted(StrictModel):
    """A state's completion condition became true."""

    kind: Literal["state_completed"] = "state_completed"
    state_id: str


class TransitionTaken(StrictModel):
    """The session moved from one state to another."""

    kind: Literal["transition_taken"] = "transition_taken"
    source_id: str
    target_id: str


class ActionExecuted(StrictModel):
    """A state that performs a side effect completed — the host ran it."""

    kind: Literal["action_executed"] = "action_executed"
    state_id: str


class StateReopened(StrictModel):
    """A completed state was invalidated because data it depends on changed.

    ``had_executed`` is true when this state had already run a side effect, so the
    host knows it must compensate (e.g. resend to the corrected address).
    """

    kind: Literal["state_reopened"] = "state_reopened"
    state_id: str
    had_executed: bool


Event = Annotated[
    ValueSet | ValueChanged | StateCompleted | TransitionTaken | ActionExecuted | StateReopened,
    Field(discriminator="kind"),
]
"""Anything recorded in a session's history."""
