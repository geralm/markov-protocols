"""0.4.0: the workflow field namespace — reference validation + Blackboard bounding."""

from markov_protocols import (
    ActionExecuteState,
    DataCollectionState,
    ErrorType,
    Ref,
    Requirement,
    Session,
    Transition,
    Workflow,
    from_yaml,
    to_yaml,
)


def _action_referencing(field: str, **compile_kwargs: object) -> object:
    state = ActionExecuteState(
        title="Send", requires=[Requirement(field="sent")], payload={"to": Ref(field=field)}
    )
    return Workflow.compile(name="w", initial="Send", states=[state], **compile_kwargs)  # type: ignore[arg-type]


def test_reference_to_an_unknown_field_fails_compilation() -> None:
    result = _action_referencing("email")  # nothing declares 'email'
    assert result.is_failure  # type: ignore[attr-defined]
    assert result.error is ErrorType.NOT_FOUND  # type: ignore[attr-defined]
    assert "email" in str(result.error_details)  # type: ignore[attr-defined]


def test_reference_to_a_collected_field_compiles() -> None:
    # 'email' is collected by an earlier state -> in the namespace.
    workflow = Workflow.compile(
        name="w",
        initial="Collect email",
        states=[
            DataCollectionState(title="Collect email", requires=[Requirement(field="email")]),
            ActionExecuteState(
                title="Send",
                requires=[Requirement(field="sent")],
                payload={"to": Ref(field="email")},
            ),
        ],
        transitions=[Transition(source_id="collect-email", target_id="send")],
    )
    assert workflow.is_success


def test_reference_to_a_declared_external_field_compiles() -> None:
    result = _action_referencing("email", external_fields=["email"])
    assert result.is_success  # type: ignore[attr-defined]


def test_fields_is_derived_from_requires_plus_external() -> None:
    workflow = Workflow.compile(
        name="w",
        initial="Collect",
        states=[DataCollectionState(title="Collect", requires=[Requirement(field="name")])],
        external_fields=["customer_id"],
    ).value
    assert workflow.fields == {"name", "customer_id"}


def test_update_drops_unknown_keys_and_reports_them() -> None:
    workflow = Workflow.compile(
        name="w",
        initial="Collect",
        states=[DataCollectionState(title="Collect", requires=[Requirement(field="name")])],
    ).value
    session = Session.start(workflow)
    result = session.update({"name": "Ana", "junk": "x", "noise": 1}).value
    assert result.ignored_fields == ["junk", "noise"]  # reported...
    assert session.blackboard.to_dict() == {"name": "Ana"}  # ...but never stored


def test_external_fields_survive_serialization() -> None:
    workflow = Workflow.compile(
        name="w",
        initial="Collect",
        states=[DataCollectionState(title="Collect", requires=[Requirement(field="name")])],
        external_fields=["customer_id"],
    ).value
    restored = from_yaml(to_yaml(workflow)).value
    assert restored.external_fields == ("customer_id",)
    assert restored == workflow


def test_known_keys_are_kept() -> None:
    workflow = Workflow.compile(
        name="w",
        initial="Collect",
        states=[DataCollectionState(title="Collect", requires=[Requirement(field="name")])],
        external_fields=["locale"],
    ).value
    session = Session.start(workflow)
    result = session.update({"name": "Ana", "locale": "es"}).value
    assert result.ignored_fields == []
    assert session.blackboard.to_dict() == {"name": "Ana", "locale": "es"}
