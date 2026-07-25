"""A state that completes once the user has provided the required data."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ...conditions.models import Condition
from ..state import Requirement, State, all_of, requirement_condition


class DataCollectionState(State):
    """Completes when every requirement is satisfied on the Blackboard.

    The data is produced by the host's LLM extracting it from the conversation;
    this state only declares *what* is needed, never *how* to obtain it.
    """

    type: Literal["DATA_COLLECTION"] = "DATA_COLLECTION"
    requires: list[Requirement] = Field(min_length=1)

    def completion_condition(self) -> Condition:
        return all_of([requirement_condition(r) for r in self.requires])

    def depends_on(self) -> set[str]:
        return {r.field for r in self.requires}
