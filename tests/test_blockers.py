"""blockers & rendering: every state explains why it hasn't advanced, in facts."""

from markov_protocols import (
    ActionExecuteState,
    BlockReason,
    DataCollectionState,
    HumanHandoffState,
    Option,
    Ref,
    Regex,
    Requirement,
    Session,
    Transition,
    Workflow,
)


def _intent_state() -> DataCollectionState:
    return DataCollectionState(
        title="Detect intent",
        requires=[
            Requirement(
                field="intent",
                description="what the customer wants",
                options=[
                    Option(value="buy", description="wants to purchase"),
                    Option(value="support", description="needs help"),
                ],
            )
        ],
    )


def _single(workflow: Workflow) -> Session:
    return Session.start(workflow)


def test_absent_field_is_a_missing_blocker() -> None:
    workflow = Workflow.compile(name="q", initial="Detect intent", states=[_intent_state()]).value
    result = _single(workflow).update({}).value
    assert result.missing_fields == ["intent"]
    assert result.invalid_fields == []
    assert result.blockers[0].reason is BlockReason.MISSING


def test_present_but_disallowed_value_is_an_invalid_blocker() -> None:
    workflow = Workflow.compile(name="q", initial="Detect intent", states=[_intent_state()]).value
    result = _single(workflow).update({"intent": "rent"}).value
    assert result.missing_fields == []  # it IS present...
    assert result.invalid_fields == ["intent"]  # ...but not allowed
    assert result.blockers[0].reason is BlockReason.INVALID


def test_invalid_blocker_text_lists_the_allowed_values_with_descriptions() -> None:
    workflow = Workflow.compile(name="q", initial="Detect intent", states=[_intent_state()]).value
    result = _single(workflow).update({"intent": "rent"}).value
    text = result.blockers[0].to_llm_extended()
    assert "buy (wants to purchase)" in text and "support (needs help)" in text


def test_options_auto_enforce_the_allowed_set() -> None:
    workflow = Workflow.compile(name="q", initial="Detect intent", states=[_intent_state()]).value
    session = _single(workflow)
    session.update({"intent": "rent"})
    assert session.is_finished is False  # disallowed value does not complete
    session.update({"intent": "buy"})
    assert session.is_finished is True  # allowed value does


def test_regex_invalid_value_is_reported_as_invalid_not_missing() -> None:
    state = DataCollectionState(
        title="Collect email",
        requires=[
            Requirement(field="email", condition=Regex(field="email", value="^[^@]+@[^@]+$"))
        ],
    )
    workflow = Workflow.compile(name="e", initial="Collect email", states=[state]).value
    result = _single(workflow).update({"email": "notanemail"}).value
    assert result.invalid_fields == ["email"] and result.missing_fields == []


def test_action_state_awaits_its_result_while_the_directive_tracks_inputs() -> None:
    state = ActionExecuteState(
        title="Send", requires=[Requirement(field="sent")], payload={"to": Ref(field="email")}
    )
    workflow = Workflow.compile(name="a", initial="Send", states=[state]).value
    session = _single(workflow)

    # The state always awaits its own result; the directive reports it can't run
    # yet because the payload ref (email) is missing.
    first = session.update({}).value
    assert first.blockers[0].reason is BlockReason.AWAITING_RESULT
    assert first.awaiting == ["sent"]
    assert first.directive is not None and first.directive.ready is False
    assert first.directive.missing == ["email"]

    # Once the input arrives the directive is ready; still awaiting the result.
    ready = session.update({"email": "a@b"}).value
    assert ready.directive is not None and ready.directive.ready is True
    assert ready.blockers[0].reason is BlockReason.AWAITING_RESULT


def test_handoff_awaits_a_human() -> None:
    state = HumanHandoffState(title="Escalate", requires=[Requirement(field="resolved")])
    workflow = Workflow.compile(name="h", initial="Escalate", states=[state]).value
    result = _single(workflow).update({}).value
    assert result.blockers[0].reason is BlockReason.AWAITING_HUMAN
    assert result.awaiting == ["resolved"]


def test_field_options_surfaces_descriptions_and_pattern() -> None:
    state = DataCollectionState(
        title="Signup",
        requires=[
            Requirement(field="intent", description="goal", options=[Option(value="buy")]),
            Requirement(field="email", condition=Regex(field="email", value="^.+@.+$")),
        ],
    )
    options = state.field_options()
    assert options["intent"]["description"] == "goal"
    assert options["intent"]["options"] == [{"value": "buy", "description": None}]
    assert options["email"]["pattern"] == "^.+@.+$"


def test_update_result_renders_a_factual_brief_without_prompts() -> None:
    intent = _intent_state()
    intent.metadata.prompts["ask"] = "SECRET BUSINESS PROMPT"  # must NOT leak into rendering
    workflow = Workflow.compile(name="q", initial="Detect intent", states=[intent]).value
    text = _single(workflow).update({"intent": "rent"}).value.to_llm_extended()
    assert "Detect intent" in text and "buy" in text
    assert "SECRET BUSINESS PROMPT" not in text  # facts only, no policy


def test_workflow_renders_its_structure_in_order() -> None:
    workflow = Workflow.compile(
        name="flow",
        initial="Detect intent",
        states=[
            _intent_state(),
            ActionExecuteState(title="Do it", requires=[Requirement(field="done")]),
        ],
        transitions=[Transition(source_id="detect-intent", target_id="do-it")],
    ).value
    text = workflow.to_llm_extended()
    assert "1. Detect intent" in text and "2. Do it" in text
    assert "Detect intent -> Do it" in text
