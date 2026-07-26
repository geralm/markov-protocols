"""workflow: compile() proves a graph runnable and orders transitions deterministically."""

from markov_protocols import (
    ActionExecuteState,
    DataCollectionState,
    ErrorType,
    Ref,
    Requirement,
    Transition,
    Workflow,
)


def _collect(title: str = "Collect Customer Data") -> DataCollectionState:
    return DataCollectionState(title=title, requires=[Requirement(field="email")])


def _action(title: str = "Send Confirmation") -> ActionExecuteState:
    return ActionExecuteState(title=title, requires=[Requirement(field="sent")])


def test_valid_graph_compiles_and_slugs_the_initial() -> None:
    result = Workflow.compile(
        name="w",
        initial="Collect Customer Data",
        states=[_collect(), _action()],
        transitions=[Transition(source_id="collect-customer-data", target_id="send-confirmation")],
    )
    assert result.is_success
    assert result.value.initial_id == "collect-customer-data"


def test_outgoing_orders_by_priority_then_declaration() -> None:
    states = [_collect("A"), _action("B"), _action("C")]
    low = Transition(source_id="a", target_id="b", priority=1)
    high = Transition(source_id="a", target_id="c", priority=5)
    workflow = Workflow.compile(name="w", initial="A", states=states, transitions=[low, high]).value
    # Higher priority wins regardless of declaration order.
    assert [t.target_id for t in workflow.outgoing("a")] == ["c", "b"]


def test_outgoing_breaks_ties_by_declaration_order() -> None:
    states = [_collect("A"), _action("B"), _action("C")]
    first = Transition(source_id="a", target_id="b")
    second = Transition(source_id="a", target_id="c")
    workflow = Workflow.compile(
        name="w", initial="A", states=states, transitions=[first, second]
    ).value
    assert [t.target_id for t in workflow.outgoing("a")] == ["b", "c"]


def test_duplicate_slug_is_a_conflict() -> None:
    result = Workflow.compile(
        name="w", initial="Same Title", states=[_collect("Same Title"), _action("Same Title")]
    )
    assert result.is_failure and result.error is ErrorType.CONFLICT


def test_unknown_transition_endpoint_is_not_found() -> None:
    result = Workflow.compile(
        name="w",
        initial="Collect Customer Data",
        states=[_collect()],
        transitions=[Transition(source_id="collect-customer-data", target_id="ghost")],
    )
    assert result.is_failure and result.error is ErrorType.NOT_FOUND


def test_unknown_initial_is_not_found() -> None:
    result = Workflow.compile(name="w", initial="Ghost", states=[_collect()])
    assert result.is_failure and result.error is ErrorType.NOT_FOUND


def test_empty_workflow_is_a_validation_error() -> None:
    result = Workflow.compile(name="w", initial="anything", states=[])
    assert result.is_failure and result.error is ErrorType.VALIDATION_ERROR


def test_graph_errors_return_a_result_and_never_raise() -> None:
    # A duplicate-slug graph must come back as a failed Result, not an exception.
    result = Workflow.compile(name="w", initial="T", states=[_collect("T"), _action("T")])
    assert result.is_failure


def test_workflow_round_trips_through_json_preserving_types() -> None:
    workflow = Workflow.compile(
        name="w",
        initial="Collect Customer Data",
        states=[
            _collect(),
            ActionExecuteState(
                title="Send Confirmation",
                requires=[Requirement(field="sent")],
                payload={"to": Ref(field="email")},
            ),
        ],
        transitions=[Transition(source_id="collect-customer-data", target_id="send-confirmation")],
    ).value
    restored = Workflow.model_validate(workflow.model_dump())
    assert restored == workflow
    assert [type(s).__name__ for s in restored.states] == [
        "DataCollectionState",
        "ActionExecuteState",
    ]
