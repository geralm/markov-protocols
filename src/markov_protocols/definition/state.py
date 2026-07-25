"""The ``State`` interface — the extension seam of the whole engine.

Every step in a workflow is a ``State``. The engine never branches on a state's
concrete type; it only ever asks through this interface:

* ``completion_condition()`` — the ``Condition`` that, when true over the
  Blackboard, means this step is done.
* ``depends_on()`` — the Blackboard fields whose change should reopen this step.
* ``blockers()`` — why the step has not completed yet (missing/invalid/awaiting).

Adding a new kind of state (here or downstream) means implementing these and
registering the type — with zero changes to the engine.

Note the two levels: a ``Requirement`` is an authoring input (a needed field, its
allowed ``options``, an optional rule); ``completion_condition()`` compiles those
into the single evaluable ``Condition`` the engine checks.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from pydantic import Field

from ..base import StrictModel
from ..conditions.evaluate import condition_fields, evaluate
from ..conditions.models import All, Condition, Exists, In
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
    """A field a data-collection state needs.

    ``options`` fixes the allowed values (and auto-compiles to an ``In`` rule);
    ``condition`` adds any further rule; ``description`` explains the field to the
    agent. All are optional beyond ``field``.
    """

    field: str
    description: str | None = None
    options: list[Option] = Field(default_factory=list)
    condition: Condition | None = None


def field_present(data: Mapping[str, Any], field: str) -> bool:
    """Whether a field is present and non-null on the data."""
    return evaluate(Exists(field=field), data)


def all_of(conditions: list[Condition]) -> Condition:
    """Combine conditions with AND. A lone condition is returned unwrapped."""
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


class State(StrictModel, Renderable, ABC):
    """A single step. ``id`` is derived from ``title`` and is never stored."""

    title: str
    metadata: StateMetadata = StateMetadata()

    @property
    def id(self) -> str:
        """The deterministic identifier: the slug of the title."""
        return slugify(self.title)

    @abstractmethod
    def completion_condition(self) -> Condition:
        """The condition that, when true over the Blackboard, marks this state done."""

    @abstractmethod
    def depends_on(self) -> set[str]:
        """Blackboard fields whose change should reopen this state."""

    def produces(self) -> set[str]:
        """Blackboard fields this state *outputs* when it completes.

        Empty by default (data-collection states produce nothing — the user
        supplies the data). Action/handoff states return their result field.
        When a state is reopened these fields are cleared, so an action that had
        already run is forced to run again with the corrected inputs.
        """
        return set()

    def directive(self, data: Mapping[str, Any]) -> Directive | None:
        """The side effect the host must run while this state is active.

        Defaults to ``None`` — states that only wait on the user (e.g. data
        collection) surface no host action. Action/handoff states override this.
        """
        return None

    def blockers(self, data: Mapping[str, Any]) -> list[Blocker]:
        """Why this state has not completed. Empty when it has.

        Generic default: report the referenced fields that are absent. Subtypes
        refine this into precise missing / invalid / awaiting reasons.
        """
        if evaluate(self.completion_condition(), data):
            return []
        absent = sorted(
            f for f in condition_fields(self.completion_condition()) if not field_present(data, f)
        )
        if absent:
            return [
                Blocker(reason=BlockReason.MISSING, field=f, detail=f"'{f}' is required")
                for f in absent
            ]
        return [
            Blocker(
                reason=BlockReason.INVALID,
                field=None,
                detail=f"the data does not satisfy step '{self.title}'",
            )
        ]

    def to_llm_extended(self) -> str:
        return f"Step: {self.title}"
