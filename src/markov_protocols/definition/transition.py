"""A guarded, prioritized directed link between two states."""

from __future__ import annotations

from ..base import StrictModel
from ..conditions.models import Condition
from .metadata import TransitionMetadata


class Transition(StrictModel):
    """A move from ``source_id`` to ``target_id``.

    A transition is *enabled* when its source has completed and its ``guard`` (if
    any) holds. When several are enabled from one state, ``priority`` (higher first)
    then declaration order breaks the tie — a total order, so the choice is always
    deterministic.
    """

    source_id: str
    target_id: str
    guard: Condition | None = None
    priority: int = 0
    metadata: TransitionMetadata = TransitionMetadata()
