"""0.3.0: optional requirements, Requirement.type, and to_pydantic_model / expected_fields."""

import pytest
from pydantic import ValidationError

from markov_protocols import (
    ActionExecuteState,
    DataCollectionState,
    Option,
    Ref,
    Regex,
    Requirement,
    Session,
    ValueType,
    Workflow,
)


def _collect(*requires: Requirement) -> Workflow:
    return Workflow.compile(
        name="w",
        initial="Collect",
        states=[DataCollectionState(title="Collect", requires=list(requires))],
    ).value


def test_optional_requirement_never_blocks() -> None:
    workflow = _collect(
        Requirement(field="name"),
        Requirement(field="phone", required=False),
    )
    session = Session.start(workflow)
    result = session.update({"name": "Ana"}).value  # phone omitted
    assert session.is_finished is True  # optional field did not gate completion
    assert result.missing_fields == []


def test_all_optional_state_completes_immediately() -> None:
    workflow = _collect(Requirement(field="note", required=False))
    session = Session.start(workflow)
    assert session.update({}).value.is_finished is True  # nothing required -> vacuously complete


def test_optional_value_is_captured_when_provided() -> None:
    workflow = _collect(Requirement(field="name"), Requirement(field="phone", required=False))
    session = Session.start(workflow)
    session.update({"name": "Ana", "phone": "555"})
    assert session.blackboard.get("phone") == "555"  # rode along, stored


def test_expected_fields_is_uniform_across_state_types() -> None:
    collect = DataCollectionState(title="c", requires=[Requirement(field="email")])
    action = ActionExecuteState(
        title="a", requires=[Requirement(field="done", type=ValueType.BOOLEAN)]
    )
    assert [r.field for r in collect.expected_fields()] == ["email"]
    assert [r.field for r in action.expected_fields()] == ["done"]  # same method, any state


def test_to_pydantic_model_marks_required_and_optional() -> None:
    state = DataCollectionState(
        title="Signup",
        requires=[
            Requirement(field="name", description="the name"),
            Requirement(field="age", type=ValueType.INTEGER),
            Requirement(field="phone", required=False),
        ],
    )
    schema = state.to_pydantic_model().model_json_schema()
    assert set(schema["required"]) == {"name", "age"}  # optional 'phone' is not required
    assert schema["properties"]["age"]["type"] == "integer"
    assert schema["properties"]["name"]["description"] == "the name"


def test_to_pydantic_model_renders_options_as_an_enum() -> None:
    state = DataCollectionState(
        title="Triage",
        requires=[
            Requirement(field="intent", options=[Option(value="buy"), Option(value="support")])
        ],
    )
    schema = state.to_pydantic_model().model_json_schema()
    assert schema["properties"]["intent"]["enum"] == ["buy", "support"]


def test_to_pydantic_model_validates_extracted_results() -> None:
    state = DataCollectionState(
        title="Triage",
        requires=[
            Requirement(field="intent", options=[Option(value="buy"), Option(value="support")]),
            Requirement(field="age", type=ValueType.INTEGER),
        ],
    )
    model = state.to_pydantic_model()
    # A well-formed extraction validates and can feed update().
    ok = model.model_validate({"intent": "buy", "age": 30})
    assert ok.model_dump() == {"intent": "buy", "age": 30}
    # A disallowed enum value is rejected by validation.
    with pytest.raises(ValidationError):
        model.model_validate({"intent": "rent", "age": 30})


def test_action_result_can_be_typed_and_validated() -> None:
    action = ActionExecuteState(
        title="Send",
        payload={"to": Ref(field="email")},
        requires=[Requirement(field="sent", type=ValueType.BOOLEAN)],
    )
    schema = action.to_pydantic_model().model_json_schema()
    assert schema["properties"]["sent"]["type"] == "boolean"  # reusable across state types


def test_regex_requirement_becomes_a_pattern_in_the_schema() -> None:
    state = DataCollectionState(
        title="Email",
        requires=[Requirement(field="email", condition=Regex(field="email", value="^.+@.+$"))],
    )
    schema = state.to_pydantic_model().model_json_schema()
    assert schema["properties"]["email"]["pattern"] == "^.+@.+$"


def test_field_options_reports_required_flag_and_type() -> None:
    state = DataCollectionState(
        title="c",
        requires=[Requirement(field="name"), Requirement(field="phone", required=False)],
    )
    options = state.field_options()
    assert options["name"]["required"] is True
    assert options["phone"]["required"] is False
    assert options["name"]["type"] == "string"
