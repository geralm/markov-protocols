"""State and transition metadata: typed-but-open policy carriers.

The reserved sections are the shape the machine relies on being *present*; their
contents are opaque business policy the machine never interprets. ``extra="allow"``
(via ``StrictOpenModel``) lets authors attach anything beyond the reserved keys.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ..base import StrictOpenModel


class StateMetadata(StrictOpenModel):
    """Policy attached to a state. Contents are opaque to the machine."""

    tools: dict[str, Any] = Field(default_factory=dict)
    prompts: dict[str, Any] = Field(default_factory=dict)
    guardrails: dict[str, Any] = Field(default_factory=dict)


class TransitionMetadata(StrictOpenModel):
    """Policy attached to a transition. Contents are opaque to the machine."""

    events: dict[str, Any] = Field(default_factory=dict)
    resources: dict[str, Any] = Field(default_factory=dict)
    reward: float = Field(default=1.0, ge=0.0, description="Transition reward (experimental)")
