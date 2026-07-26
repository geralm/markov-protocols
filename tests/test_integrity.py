"""integrity: corrections reopen the right states and force compensation.

This is the reliability payoff — when a customer changes their mind mid-conversation,
the machine rewinds deterministically, tells the agent, and makes side effects re-run.
"""

from markov_protocols import (
    ActionExecuted,
    ActionExecuteState,
    DataCollectionState,
    Ref,
    Requirement,
    Session,
    StateReopened,
    Status,
    Transition,
    Workflow,
)


def _real_estate_workflow() -> Workflow:
    # collect-email -> send-confirmation (action, uses email) -> collect-budget
    return Workflow.compile(
        name="real-estate",
        initial="Collect email",
        states=[
            DataCollectionState(title="Collect email", requires=[Requirement(field="email")]),
            ActionExecuteState(
                title="Send confirmation",
                requires=[Requirement(field="sent")],
                payload={"to": Ref(field="email")},
            ),
            DataCollectionState(title="Collect budget", requires=[Requirement(field="budget")]),
        ],
        transitions=[
            Transition(source_id="collect-email", target_id="send-confirmation"),
            Transition(source_id="send-confirmation", target_id="collect-budget"),
        ],
    ).value


def _run_to_completion(session: Session) -> None:
    session.update({"email": "pedro@x"})
    session.update({"sent": True})  # host runs the confirmation
    session.update({"budget": 5000})


def test_an_action_records_that_it_executed() -> None:
    session = Session.start(_real_estate_workflow())
    session.update({"email": "pedro@x"})
    result = session.update({"sent": True})
    assert any(
        isinstance(e, ActionExecuted) and e.state_id == "send-confirmation"
        for e in result.value.events
    )


def test_a_correction_reopens_the_tail_and_rewinds_to_the_earliest_state() -> None:
    session = Session.start(_real_estate_workflow())
    _run_to_completion(session)
    assert session.is_finished

    result = session.update({"email": "nonpedro@y"})
    reopened = [e.state_id for e in result.value.events if isinstance(e, StateReopened)]
    assert reopened == ["collect-email", "send-confirmation", "collect-budget"]
    # Rewound to the start, re-completed the email step, and halted at the action.
    assert session.current_state.id == "send-confirmation"


def test_reopen_flags_had_executed_only_for_the_state_that_ran_a_side_effect() -> None:
    session = Session.start(_real_estate_workflow())
    _run_to_completion(session)
    result = session.update({"email": "nonpedro@y"})
    flags = {
        e.state_id: e.had_executed
        for e in result.value.events
        if isinstance(e, StateReopened)
    }
    assert flags == {
        "collect-email": False,
        "send-confirmation": True,  # the confirmation was sent — host must compensate
        "collect-budget": False,
    }


def test_reopened_action_output_is_cleared_and_redirected_to_the_new_value() -> None:
    session = Session.start(_real_estate_workflow())
    _run_to_completion(session)
    result = session.update({"email": "nonpedro@y"})
    assert session.blackboard.get("sent") is None  # stale result dropped
    directive = result.value.directive
    assert directive is not None and directive.ready is True
    assert directive.payload == {"to": "nonpedro@y"}  # will resend to the corrected address


def test_the_workflow_resettles_once_the_action_reruns() -> None:
    session = Session.start(_real_estate_workflow())
    _run_to_completion(session)
    session.update({"email": "nonpedro@y"})  # reopened; parked at the action
    assert session.current_state.id == "send-confirmation"
    session.update({"sent": True})  # host resends
    # budget (5000) is still on the board, so the tail completes for free.
    assert session.is_finished is True


def test_a_change_only_reopens_states_that_depend_on_that_field() -> None:
    workflow = Workflow.compile(
        name="two-steps",
        initial="Collect email",
        states=[
            DataCollectionState(title="Collect email", requires=[Requirement(field="email")]),
            DataCollectionState(title="Collect budget", requires=[Requirement(field="budget")]),
        ],
        transitions=[Transition(source_id="collect-email", target_id="collect-budget")],
    ).value
    session = Session.start(workflow)
    session.update({"email": "a@b"})
    session.update({"budget": 1000})

    result = session.update({"budget": 2000})  # only the budget step depends on budget
    reopened = [e.state_id for e in result.value.events if isinstance(e, StateReopened)]
    assert reopened == ["collect-budget"]
    assert session.statuses["collect-email"] is Status.COMPLETED  # untouched


def test_resubmitting_an_unchanged_value_reopens_nothing() -> None:
    session = Session.start(_real_estate_workflow())
    _run_to_completion(session)
    result = session.update({"email": "pedro@x"})  # same value as before
    assert not any(isinstance(e, StateReopened) for e in result.value.events)
    assert session.is_finished is True
