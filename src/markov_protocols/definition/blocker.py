"""``Blocker`` — a structured, renderable reason a state has not completed.

Every state answers the same question through ``State.blockers()``: *why haven't
you advanced?* Each reason is one ``Blocker`` — structured for host logic
(``reason``, ``field``) and renderable to text for the agent (``detail``).
"""

from __future__ import annotations

from enum import StrEnum

from ..base import StrictModel
from ..renderable import Renderable


class BlockReason(StrEnum):
    """Why a field (or the whole step) is holding the workflow."""

    MISSING = "MISSING"  # a required field is absent
    INVALID = "INVALID"  # a field is present but fails its rule
    AWAITING_RESULT = "AWAITING_RESULT"  # waiting for the host to run an action
    AWAITING_HUMAN = "AWAITING_HUMAN"  # waiting for a human to resolve a handoff


class Blocker(StrictModel, Renderable):
    """One reason the current state has not completed."""

    reason: BlockReason
    field: str | None = None
    detail: str  # a factual, prompt-ready explanation

    def to_llm_extended(self) -> str:
        return self.detail

    def __str__(self) -> str:
        return self.detail
