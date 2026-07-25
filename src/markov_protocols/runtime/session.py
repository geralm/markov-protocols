"""The Session: one conversation's live run of a workflow.

``Session`` is the facade the host uses. ``update(values)`` is the single input
verb; in this slice it runs two passes:

1. **Record** the new values, diffing them into events.
2. **Fast-forward**: while the current state is complete and a transition is
   enabled, take it. One call can therefore advance through many states when the
   user supplies everything at once, and hold position when they don't.

(The integrity/rewind pass that reacts to ``ValueChanged`` arrives in Slice 3;
here changes are recorded but not yet acted upon.)
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ..conditions.evaluate import condition_fields, evaluate
from ..conditions.models import Exists
from ..definition.state import Directive, State, Status
from ..definition.transition import Transition
from ..definition.workflow import Workflow
from ..result import Result
from .blackboard import Blackboard
from .events import (
    ActionExecuted,
    Event,
    StateCompleted,
    StateReopened,
    TransitionTaken,
    ValueChanged,
)


@dataclass(frozen=True)
class UpdateResult:
    """What one ``update()`` produced — the agent's deterministic snapshot."""

    current_state: State
    missing_fields: list[str]
    available_transitions: list[Transition]
    directive: Directive | None
    events: list[Event]
    is_finished: bool


class Session:
    """A running workflow: a workflow, a blackboard, a cursor, and a history."""

    def __init__(
        self,
        *,
        id: str,
        workflow: Workflow,
        blackboard: Blackboard,
        current_id: str,
        statuses: dict[str, Status],
        history: list[Event],
    ) -> None:
        self.id = id
        self._workflow = workflow
        self._blackboard = blackboard
        self._current_id = current_id  # the cursor: id of the state we are sitting on
        self._statuses = statuses
        self._history = history

    # --- construction --------------------------------------------------

    @classmethod
    def start(cls, workflow: Workflow) -> Session:
        """Begin a fresh run at the workflow's initial state."""
        statuses = {state.id: Status.PENDING for state in workflow.states}
        statuses[workflow.initial_id] = Status.ACTIVE
        return cls(
            id=str(uuid.uuid4()),
            workflow=workflow,
            blackboard=Blackboard(),
            current_id=workflow.initial_id,
            statuses=statuses,
            history=[],
        )

    @classmethod
    def resume(
        cls,
        workflow: Workflow,
        *,
        id: str,
        values: Mapping[str, Any],
        current_id: str,
        statuses: Mapping[str, Status],
        history: list[Event],
    ) -> Session:
        """Rehydrate a persisted run from its saved pieces."""
        return cls(
            id=id,
            workflow=workflow,
            blackboard=Blackboard(values),
            current_id=current_id,
            statuses=dict(statuses),
            history=list(history),
        )

    # --- inspection ----------------------------------------------------

    @property
    def current_state(self) -> State:
        state = self._workflow.state(self._current_id)
        assert state is not None  # invariant: the cursor always names a real state
        return state

    @property
    def blackboard(self) -> Blackboard:
        return self._blackboard

    @property
    def history(self) -> list[Event]:
        return list(self._history)

    @property
    def statuses(self) -> dict[str, Status]:
        return dict(self._statuses)

    @property
    def is_finished(self) -> bool:
        """True when the current state has completed and there is nowhere left to go."""
        current_is_done = self._statuses[self._current_id] is Status.COMPLETED
        no_way_out = not self._workflow.outgoing(self._current_id)
        return current_is_done and no_way_out

    # --- execution -----------------------------------------------------

    def update(self, values: Mapping[str, Any]) -> Result[UpdateResult, str]:
        """Apply new values, then settle the workflow forward as far as it can go."""
        # Pass 1: record the incoming data. Each field that actually changed
        # becomes one event (unchanged fields produce nothing).
        events = list(self._blackboard.write(values))

        # Pass 2 (integrity): if a correction invalidated an already-completed
        # state, rewind to it before moving forward again.
        events.extend(self._reopen_states_invalidated_by(events))

        # Pass 3: advance through every state the data already satisfies.
        events.extend(self._fast_forward())

        # Everything that happened this call is appended to the permanent history.
        self._history.extend(events)
        return Result.ok(self._snapshot(events))

    def _fast_forward(self) -> list[Event]:
        """Step the cursor forward while the data allows, returning what happened.

        The loop stops when the current state is not yet complete (we wait here),
        when no transition is enabled (finished or stuck), or when the next step
        would re-enter a state we already visited this call (a loop — we never spin).
        """
        events: list[Event] = []

        # Track where we have been *during this call* so a cyclic graph cannot loop
        # forever: the blackboard does not change mid-pass, so re-entering a state
        # would repeat identically.
        visited_this_call = {self._current_id}

        while True:
            # 1. If the state under the cursor is not complete, we have gone as far
            #    as this data allows. Wait here for the next update.
            if not self._current_state_is_complete():
                break

            # 2. Mark it complete (records an event the first time only). If the
            #    state performs a side effect, that completion means the host ran it.
            just_completed = self._mark_current_completed()
            if just_completed is not None:
                events.append(just_completed)
                if self.current_state.produces():
                    events.append(ActionExecuted(state_id=self._current_id))

            # 3. Pick the one deterministic next transition. None means dead-end.
            next_step = self._choose_next_transition()
            if next_step is None:
                break

            # 4. Refuse to re-enter a state already seen this call (loop guard).
            if next_step.target_id in visited_this_call:
                break

            # 5. Take the step and remember the target.
            events.append(self._take_transition(next_step))
            visited_this_call.add(next_step.target_id)

        return events

    # --- integrity: reopening on a correction --------------------------

    def _reopen_states_invalidated_by(self, write_events: list[Event]) -> list[Event]:
        """React to corrections: reopen any completed state whose data just changed.

        A state is only affected when a field it *depends on* was overwritten
        (a ``ValueChanged``). Brand-new fields never invalidate past work.
        """
        changed_fields = {e.field for e in write_events if isinstance(e, ValueChanged)}
        if not changed_fields:
            return []

        invalidated = [
            state
            for state in self._workflow.states
            if self._statuses[state.id] is Status.COMPLETED
            and (state.depends_on() & changed_fields)
        ]
        if not invalidated:
            return []
        return self._rewind_to_earliest(invalidated)

    def _rewind_to_earliest(self, reopened_states: list[State]) -> list[Event]:
        """Strict rewind: go back to the earliest reopened state and redo the tail.

        "Earliest" is read straight from history — the order in which states first
        completed. Every state that completed at or after that point is invalidated,
        so the workflow re-walks the whole tail with the corrected data.
        """
        completed_at = self._completion_order()
        earliest_id = min((s.id for s in reopened_states), key=lambda sid: completed_at[sid])
        cutoff = completed_at[earliest_id]

        invalidated = [
            state
            for state in self._workflow.states
            if self._statuses[state.id] is Status.COMPLETED
            and completed_at.get(state.id, -1) >= cutoff
        ]

        events: list[Event] = []
        for state in invalidated:
            # An actionable state that had completed has already run its side effect.
            events.append(StateReopened(state_id=state.id, had_executed=bool(state.produces())))
            self._clear_outputs(state)  # force actions to run again with new inputs
            self._statuses[state.id] = Status.PENDING

        # The earliest reopened state becomes the cursor again, marked REOPENED.
        self._statuses[earliest_id] = Status.REOPENED
        self._current_id = earliest_id
        return events

    def _completion_order(self) -> dict[str, int]:
        """Map each state to the position it *first* completed in history."""
        order: dict[str, int] = {}
        for index, event in enumerate(self._history):
            if isinstance(event, StateCompleted) and event.state_id not in order:
                order[event.state_id] = index
        return order

    def _clear_outputs(self, state: State) -> None:
        """Drop a reopened state's produced fields so it cannot re-complete on stale output."""
        for field in state.produces():
            self._blackboard.remove(field)

    # --- small, single-purpose helpers ---------------------------------

    def _current_state_is_complete(self) -> bool:
        """Does the current state's completion condition hold over the blackboard?"""
        return evaluate(self.current_state.completion_condition(), self._blackboard)

    def _mark_current_completed(self) -> StateCompleted | None:
        """Set the current state to COMPLETED; return an event only if it just changed."""
        if self._statuses[self._current_id] is Status.COMPLETED:
            return None  # already completed earlier — nothing new to record
        self._statuses[self._current_id] = Status.COMPLETED
        return StateCompleted(state_id=self._current_id)

    def _choose_next_transition(self) -> Transition | None:
        """The first enabled transition in deterministic order, or None if there is none."""
        enabled = self._enabled_transitions(self._current_id)
        return enabled[0] if enabled else None

    def _take_transition(self, transition: Transition) -> TransitionTaken:
        """Move the cursor to the target, wake it if new, and describe the move."""
        source_id = self._current_id
        self._current_id = transition.target_id
        if self._statuses[transition.target_id] is Status.PENDING:
            self._statuses[transition.target_id] = Status.ACTIVE
        return TransitionTaken(source_id=source_id, target_id=transition.target_id)

    def _enabled_transitions(self, state_id: str) -> list[Transition]:
        """Transitions that may be taken from ``state_id`` right now.

        A transition is enabled only when its source has completed and its guard (if
        any) holds. They are returned in the workflow's deterministic order, so the
        first one is always the unambiguous choice.
        """
        if self._statuses[state_id] is not Status.COMPLETED:
            return []
        return [t for t in self._workflow.outgoing(state_id) if self._guard_allows(t)]

    def _guard_allows(self, transition: Transition) -> bool:
        """A transition with no guard is always allowed; otherwise the guard must hold."""
        if transition.guard is None:
            return True
        return evaluate(transition.guard, self._blackboard)

    def _missing_fields(self, state: State) -> list[str]:
        """Fields the state's completion mentions that are still absent."""
        mentioned = condition_fields(state.completion_condition())
        absent = [field for field in mentioned if not self._has_value(field)]
        return sorted(absent)

    def _has_value(self, field: str) -> bool:
        """Is ``field`` present and non-null on the blackboard?"""
        return evaluate(Exists(field=field), self._blackboard)

    def _snapshot(self, events: list[Event]) -> UpdateResult:
        """Assemble the return value describing where the session now stands."""
        current = self.current_state
        return UpdateResult(
            current_state=current,
            missing_fields=self._missing_fields(current),
            available_transitions=self._enabled_transitions(self._current_id),
            directive=current.directive(self._blackboard),
            events=events,
            is_finished=self.is_finished,
        )
