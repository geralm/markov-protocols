"""The ``Workflow`` — an authored graph, and ``compile()`` that proves it runnable.

``compile()`` is deliberately named: it does not merely build an object, it validates
that the graph is ready to execute. If it returns ``ok``, a session can run the
workflow without surprises — every id is unique, every transition endpoint exists,
and the initial state is real.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pydantic import SerializeAsAny, field_validator

from ..base import StrictModel
from ..renderable import Renderable
from ..result import ErrorType, Result
from ..slug import slugify
from .registry import state_registry
from .state import State
from .transition import Transition


class Workflow(StrictModel, Renderable):
    """An immutable, validated workflow definition."""

    name: str
    # SerializeAsAny: dump each state by its concrete type (keep ``type`` + subtype
    # fields) so a workflow round-trips through JSON via the registry.
    states: tuple[SerializeAsAny[State], ...]
    transitions: tuple[Transition, ...] = ()
    initial_id: str

    @field_validator("states", mode="before")
    @classmethod
    def _parse_states(cls, value: Any) -> Any:
        if isinstance(value, (list, tuple)):
            return tuple(state_registry.parse(v) for v in value)
        return value

    @classmethod
    def compile(
        cls,
        *,
        name: str,
        states: Iterable[State | dict[str, Any]],
        initial: str,
        transitions: Iterable[Transition | dict[str, Any]] = (),
    ) -> Result[Workflow, str]:
        """Validate the graph and return a runnable ``Workflow`` (or a failure)."""
        parsed_states = tuple(state_registry.parse(s) for s in states)
        if not parsed_states:
            return Result.fail(ErrorType.VALIDATION_ERROR, "a workflow needs at least one state")

        by_id: dict[str, State] = {}
        for state in parsed_states:
            if not state.id:
                return Result.fail(
                    ErrorType.VALIDATION_ERROR,
                    f"state title {state.title!r} produces an empty id",
                )
            if state.id in by_id:
                return Result.fail(
                    ErrorType.CONFLICT,
                    f"duplicate state id {state.id!r} (titles slug to the same value)",
                )
            by_id[state.id] = state

        parsed_transitions = tuple(
            t if isinstance(t, Transition) else Transition.model_validate(t) for t in transitions
        )
        for t in parsed_transitions:
            if t.source_id not in by_id:
                return Result.fail(ErrorType.NOT_FOUND, f"unknown source state: {t.source_id!r}")
            if t.target_id not in by_id:
                return Result.fail(ErrorType.NOT_FOUND, f"unknown target state: {t.target_id!r}")

        initial_id = slugify(initial)
        if initial_id not in by_id:
            return Result.fail(ErrorType.NOT_FOUND, f"unknown initial state: {initial!r}")

        return Result.ok(
            cls(
                name=name,
                states=parsed_states,
                transitions=parsed_transitions,
                initial_id=initial_id,
            )
        )

    def state(self, state_id: str) -> State | None:
        """The state with this id, or ``None``."""
        return next((s for s in self.states if s.id == state_id), None)

    def outgoing(self, source_id: str) -> list[Transition]:
        """Transitions leaving ``source_id`` in deterministic selection order.

        Ordered by descending ``priority``, ties broken by declaration order.
        """
        matches = [t for t in self.transitions if t.source_id == source_id]
        return sorted(matches, key=lambda t: -t.priority)

    def to_llm_extended(self) -> str:
        """The workflow's structure as facts — steps in order, then transitions."""
        lines = [f"Workflow: {self.name}", "Steps:"]
        for index, state in enumerate(self.states, start=1):
            lines.append(f"{index}. {state.title}")
        if self.transitions:
            lines.append("Transitions:")
            lines.extend(f"- {self._edge_text(t)}" for t in self.transitions)
        return "\n".join(lines)

    def _edge_text(self, transition: Transition) -> str:
        source = self.state(transition.source_id)
        target = self.state(transition.target_id)
        source_title = source.title if source else transition.source_id
        target_title = target.title if target else transition.target_id
        text = f"{source_title} -> {target_title}"
        return f"{text} (conditional)" if transition.guard is not None else text
