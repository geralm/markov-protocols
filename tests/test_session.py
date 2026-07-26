"""session: the runtime guarantees — settling, branching, holding, determinism.

These tests exercise the behaviour the whole project exists for: the agent feeds
data in, and the machine advances (or waits) deterministically.
"""

from markov_protocols import (
    ActionExecuteState,
    DataCollectionState,
    Eq,
    Ref,
    Requirement,
    Session,
    StateCompleted,
    Transition,
    Workflow,
)


def _triage_workflow() -> Workflow:
    """collect-intent --(buy)--> sales-flow / --(support)--> support-flow."""
    return Workflow.compile(
        name="triage",
        initial="Collect intent",
        states=[
            DataCollectionState(title="Collect intent", requires=[Requirement(field="intent")]),
            DataCollectionState(title="Sales flow", requires=[Requirement(field="budget")]),
            DataCollectionState(title="Support flow", requires=[Requirement(field="issue")]),
        ],
        transitions=[
            Transition(
                source_id="collect-intent",
                target_id="sales-flow",
                guard=Eq(field="intent", value="buy"),
            ),
            Transition(
                source_id="collect-intent",
                target_id="support-flow",
                guard=Eq(field="intent", value="support"),
            ),
        ],
    ).value


def test_start_places_the_cursor_on_the_initial_state() -> None:
    session = Session.start(_triage_workflow())
    assert session.id  # a run always has an identity
    assert session.current_state.id == "collect-intent"
    assert session.history == []


def test_completing_a_state_advances_and_records_the_step() -> None:
    session = Session.start(_triage_workflow())
    result = session.update({"intent": "buy"})
    assert result.is_success
    assert session.current_state.id == "sales-flow"
    kinds = [type(e).__name__ for e in result.value.events]
    assert kinds == ["ValueSet", "StateCompleted", "TransitionTaken"]


def test_a_guard_routes_to_the_matching_branch() -> None:
    buy = Session.start(_triage_workflow())
    buy.update({"intent": "buy"})
    assert buy.current_state.id == "sales-flow"

    support = Session.start(_triage_workflow())
    support.update({"intent": "support"})
    assert support.current_state.id == "support-flow"


def test_one_update_fast_forwards_through_several_states() -> None:
    session = Session.start(_triage_workflow())
    # The user supplies both the intent and the branch's data at once.
    result = session.update({"intent": "buy", "budget": 1000})
    assert session.current_state.id == "sales-flow"
    completed = [e.state_id for e in result.value.events if isinstance(e, StateCompleted)]
    assert completed == ["collect-intent", "sales-flow"]


def test_missing_fields_reports_absent_data_for_the_current_state() -> None:
    session = Session.start(_triage_workflow())
    result = session.update({})
    assert session.current_state.id == "collect-intent"
    assert result.value.missing_fields == ["intent"]


def test_irrelevant_data_holds_position_the_deterministic_anchor() -> None:
    session = Session.start(_triage_workflow())
    result = session.update({"unrelated": "chit-chat"})
    assert session.current_state.id == "collect-intent"  # did not move
    assert not any(isinstance(e, StateCompleted) for e in result.value.events)
    assert result.value.missing_fields == ["intent"]


def test_an_empty_update_changes_nothing() -> None:
    session = Session.start(_triage_workflow())
    result = session.update({})
    assert result.value.events == []
    assert session.current_state.id == "collect-intent"


def test_re_submitting_the_same_value_produces_no_churn() -> None:
    workflow = Workflow.compile(
        name="one-step",
        initial="Collect email",
        states=[DataCollectionState(title="Collect email", requires=[Requirement(field="email")])],
    ).value
    session = Session.start(workflow)
    session.update({"email": "a@b"})  # completes the only state
    result = session.update({"email": "a@b"})  # same value again
    assert result.value.events == []  # no ValueChanged, no duplicate StateCompleted


def test_reaching_a_terminal_state_marks_the_session_finished() -> None:
    workflow = Workflow.compile(
        name="one-step",
        initial="Collect email",
        states=[DataCollectionState(title="Collect email", requires=[Requirement(field="email")])],
    ).value
    session = Session.start(workflow)
    assert session.is_finished is False
    session.update({"email": "a@b"})
    assert session.is_finished is True


def test_directive_is_ready_only_when_its_refs_resolve() -> None:
    workflow = Workflow.compile(
        name="notify",
        initial="Send confirmation",
        external_fields=["email"],
        states=[
            ActionExecuteState(
                title="Send confirmation",
                requires=[Requirement(field="sent")],
                payload={"to": Ref(field="email")},
            )
        ],
    ).value
    session = Session.start(workflow)

    blocked = session.update({}).value.directive
    assert blocked is not None and blocked.ready is False and blocked.missing == ["email"]

    ready = session.update({"email": "a@b"}).value.directive
    assert ready is not None and ready.ready is True and ready.payload == {"to": "a@b"}


def test_identical_runs_produce_identical_histories() -> None:
    # Determinism: same definition + same inputs -> same history (ids aside).
    def run() -> list[object]:
        session = Session.start(_triage_workflow())
        session.update({"intent": "buy"})
        session.update({"budget": 1000})
        return session.history

    assert run() == run()


def test_a_cyclic_graph_settles_instead_of_looping() -> None:
    # Both actions complete immediately from the data, and they point at each other.
    workflow = Workflow.compile(
        name="loop",
        initial="Step A",
        states=[
            ActionExecuteState(title="Step A", requires=[Requirement(field="ra")]),
            ActionExecuteState(title="Step B", requires=[Requirement(field="rb")]),
        ],
        transitions=[
            Transition(source_id="step-a", target_id="step-b"),
            Transition(source_id="step-b", target_id="step-a"),
        ],
    ).value
    session = Session.start(workflow)
    result = session.update({"ra": 1, "rb": 1})  # must terminate, not hang
    # Stopped after re-reaching an already-visited state, holding at step-b.
    assert session.current_state.id == "step-b"
    assert result.is_success


def test_data_for_future_states_is_kept_and_consumed_when_reached() -> None:
    # collect-email -> send-welcome (action) -> collect-budget
    workflow = Workflow.compile(
        name="spread",
        initial="Collect email",
        states=[
            DataCollectionState(title="Collect email", requires=[Requirement(field="email")]),
            ActionExecuteState(
                title="Send welcome",
                requires=[Requirement(field="welcomed")],
                payload={"to": Ref(field="email")},
            ),
            DataCollectionState(title="Collect budget", requires=[Requirement(field="budget")]),
        ],
        transitions=[
            Transition(source_id="collect-email", target_id="send-welcome"),
            Transition(source_id="send-welcome", target_id="collect-budget"),
        ],
    ).value
    session = Session.start(workflow)

    # The customer volunteers budget early — it belongs to a state two steps ahead.
    session.update({"email": "a@b", "budget": 5000})
    assert session.current_state.id == "send-welcome"  # held at the action
    assert session.blackboard.get("budget") == 5000  # future data retained, not dropped

    # Once the action runs, the workflow settles through the budget step for free.
    session.update({"welcomed": True})
    assert session.current_state.id == "collect-budget"
    assert session.is_finished is True


def test_resume_restores_a_run_from_its_saved_pieces() -> None:
    workflow = _triage_workflow()
    original = Session.start(workflow)
    original.update({"intent": "buy"})

    restored = Session.resume(
        workflow,
        id=original.id,
        values=original.blackboard.to_dict(),
        current_id=original.current_state.id,
        statuses=original.statuses,
        history=original.history,
    )
    assert restored.current_state.id == "sales-flow"
    assert restored.blackboard.to_dict() == {"intent": "buy"}
    # It can carry on: supplying the branch data completes it.
    restored.update({"budget": 1000})
    assert restored.statuses["sales-flow"].value == "COMPLETED"
