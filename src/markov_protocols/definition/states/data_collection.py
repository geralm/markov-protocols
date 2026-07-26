"""A state whose ``requires`` are supplied by the user (via the host's LLM).

Everything is inherited from the base ``State`` — this type only marks that the
required data comes from the user, so it produces nothing and an absent field is
``MISSING`` (both the base defaults). It just declares what it consumes.
"""

from __future__ import annotations

from typing import Literal

from ..state import State


class DataCollectionState(State):
    """Completes when its required requirements are satisfied on the Blackboard."""

    type: Literal["DATA_COLLECTION"] = "DATA_COLLECTION"

    def depends_on(self) -> set[str]:
        return {r.field for r in self.requires}
