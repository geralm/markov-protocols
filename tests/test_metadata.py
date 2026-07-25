"""metadata: reserved shape is guaranteed; business policy can extend freely."""

import pytest
from pydantic import ValidationError

from markov_protocols import StateMetadata, TransitionMetadata


def test_reserved_sections_default_to_empty() -> None:
    meta = StateMetadata()
    assert meta.tools == {} and meta.prompts == {} and meta.guardrails == {}


def test_transition_reward_defaults_to_one_and_rejects_negative() -> None:
    assert TransitionMetadata().reward == 1.0
    with pytest.raises(ValidationError):
        TransitionMetadata(reward=-1.0)


def test_metadata_accepts_extra_keys_for_extensibility() -> None:
    meta = StateMetadata(escalation_policy={"tier": 2})
    assert meta.escalation_policy == {"tier": 2}  # type: ignore[attr-defined]
