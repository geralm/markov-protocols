"""registry: the extension seam — polymorphic states survive JSON round-trip."""

import pytest

from markov_protocols import (
    ActionExecuteState,
    DataCollectionState,
    Ref,
    Requirement,
    state_registry,
)
from markov_protocols.definition.registry import StateRegistry


def test_parse_reconstructs_the_concrete_subtype() -> None:
    state = ActionExecuteState(
        title="Send", result_field="sent", payload={"to": Ref(field="email")}
    )
    restored = state_registry.parse(state.model_dump())
    assert type(restored) is ActionExecuteState
    assert restored == state


def test_parse_passes_through_existing_instances() -> None:
    state = DataCollectionState(title="c", requires=[Requirement(field="email")])
    assert state_registry.parse(state) is state


def test_parse_rejects_unknown_type() -> None:
    with pytest.raises(ValueError):
        state_registry.parse({"type": "NOT_A_STATE", "title": "x"})


def test_registry_rejects_conflicting_registration() -> None:
    registry = StateRegistry()
    registry.register(DataCollectionState)

    class Shadow(DataCollectionState):  # same "DATA_COLLECTION" tag, different class
        pass

    with pytest.raises(ValueError):
        registry.register(Shadow)
