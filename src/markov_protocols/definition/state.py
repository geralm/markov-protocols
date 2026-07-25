"""The ``State`` interface — the extension seam of the whole engine.

Every step in a workflow is a ``State``. The engine never branches on a state's
concrete type; it only ever asks two questions through this interface:

* ``completion_condition()`` — the ``Condition`` that, when true over the
  Blackboard, means this step is done.
* ``depends_on()`` — the Blackboard fields whose change should reopen this step.

Adding a new kind of state (here or in a downstream project) means implementing
these two methods and registering the type — with zero changes to the engine.

Note the two levels: a ``Requirement`` is an authoring input (a needed field with
an optional extra rule); ``completion_condition()`` compiles those into the single
evaluable ``Condition`` the engine checks.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from pydantic import Field

from ..base import StrictModel
from ..conditions.models import All, Condition, Exists
from ..slug import slugify
from .metadata import StateMetadata


class Status(StrEnum):
    """A state's lifecycle within one running session."""

    PENDING = "PENDING"  # not yet reached
    ACTIVE = "ACTIVE"  # the current step
    COMPLETED = "COMPLETED"  # its completion condition held
    REOPENED = "REOPENED"  # was completed, then data it depends on changed


class Directive(StrictModel):
    """The host-actionable instruction a state surfaces while it is active.

    The machine never acts; it hands the host a fully-resolved ``payload`` to
    execute. ``ready`` is false when a referenced field is still missing, and
    ``missing`` names those fields — so a side effect can't fire half-blank.
    """

    kind: str
    ready: bool
    payload: dict[str, Any] = Field(default_factory=dict)
    missing: list[str] = Field(default_factory=list)


class Requirement(StrictModel):
    """A field a data-collection state needs, with an optional extra condition."""

    field: str
    condition: Condition | None = None


class State(StrictModel, ABC):
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


def all_of(conditions: list[Condition]) -> Condition:
    """Combine conditions with AND. A lone condition is returned unwrapped."""
    if len(conditions) == 1:
        return conditions[0]
    return All(of=conditions)


def requirement_condition(requirement: Requirement) -> Condition:
    """A requirement holds when its field exists and its condition (if any) holds."""
    exists: Condition = Exists(field=requirement.field)
    if requirement.condition is None:
        return exists
    return All(of=[exists, requirement.condition])
