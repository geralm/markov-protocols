"""states: each state type compiles its own rules into the uniform interface.

The engine only ever calls ``completion_condition()`` and ``depends_on()``. These
tests pin what each concrete state promises through that interface — the contract
the engine relies on for every state, present and future (LSP).
"""

import pytest
from pydantic import ValidationError

from markov_protocols import (
    ActionExecuteState,
    All,
    DataCollectionState,
    Exists,
    HumanHandoffState,
    Ref,
    Regex,
    Requirement,
    State,
)


def test_id_is_the_slug_of_the_title() -> None:
    state = DataCollectionState(
        title="Collect Customer Data", requires=[Requirement(field="email")]
    )
    assert state.id == "collect-customer-data"


def test_data_collection_completes_when_all_fields_exist() -> None:
    state = DataCollectionState(
        title="collect", requires=[Requirement(field="email"), Requirement(field="name")]
    )
    assert state.completion_condition() == All(of=[Exists(field="email"), Exists(field="name")])
    assert state.depends_on() == {"email", "name"}


def test_requirement_condition_is_anded_with_existence() -> None:
    state = DataCollectionState(
        title="collect",
        requires=[Requirement(field="email", condition=Regex(field="email", value="@"))],
    )
    assert state.completion_condition() == All(
        of=[Exists(field="email"), Regex(field="email", value="@")]
    )


def test_data_collection_requires_at_least_one_field() -> None:
    with pytest.raises(ValidationError):
        DataCollectionState(title="collect", requires=[])


def test_action_completes_on_result_and_consumes_its_refs() -> None:
    state = ActionExecuteState(
        title="Send Confirmation", result_field="sent", payload={"to": Ref(field="email")}
    )
    assert state.completion_condition() == Exists(field="sent")
    assert state.depends_on() == {"email"}


def test_handoff_completes_on_resolution_and_consumes_notify_refs() -> None:
    state = HumanHandoffState(
        title="Escalate", resolution_field="resolved", notify={"who": Ref(field="agent")}
    )
    assert state.completion_condition() == Exists(field="resolved")
    assert state.depends_on() == {"agent"}


def test_state_base_is_abstract() -> None:
    with pytest.raises(TypeError):
        State(title="x")  # type: ignore[abstract]


def test_every_state_satisfies_the_engine_contract() -> None:
    states: list[State] = [
        DataCollectionState(title="c", requires=[Requirement(field="email")]),
        ActionExecuteState(title="a", result_field="result"),
        HumanHandoffState(title="h", resolution_field="resolved"),
    ]
    for state in states:
        assert state.completion_condition() is not None
        assert isinstance(state.depends_on(), set)
