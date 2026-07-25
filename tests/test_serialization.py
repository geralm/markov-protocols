"""serialization: workflows round-trip through JSON/YAML, and bad input fails cleanly."""

from pathlib import Path

import pytest

from markov_protocols import (
    ActionExecuteState,
    DataCollectionState,
    Eq,
    ErrorType,
    Ref,
    Requirement,
    Transition,
    Workflow,
    export_to_dict,
    export_to_file,
    from_json,
    from_yaml,
    import_from_dict,
    import_from_file,
    to_json,
    to_yaml,
)


def _workflow() -> Workflow:
    return Workflow.compile(
        name="intake",
        initial="Collect email",
        states=[
            DataCollectionState(title="Collect email", requires=[Requirement(field="email")]),
            ActionExecuteState(
                title="Send confirmation", result_field="sent", payload={"to": Ref(field="email")}
            ),
        ],
        transitions=[
            Transition(
                source_id="collect-email",
                target_id="send-confirmation",
                guard=Eq(field="intent", value="buy"),
            )
        ],
    ).value


def test_dict_round_trip_is_lossless() -> None:
    workflow = _workflow()
    assert import_from_dict(export_to_dict(workflow)).value == workflow


def test_json_round_trip_is_lossless() -> None:
    workflow = _workflow()
    assert from_json(to_json(workflow)).value == workflow


def test_yaml_round_trip_is_lossless() -> None:
    workflow = _workflow()
    assert from_yaml(to_yaml(workflow)).value == workflow


def test_exported_document_uses_the_friendly_shape() -> None:
    document = export_to_dict(_workflow())
    assert document["initial"] == "collect-email"  # `initial`, not `initial_id`
    assert "initial_id" not in document
    assert {s["type"] for s in document["states"]} == {"DATA_COLLECTION", "ACTION_EXECUTE"}


def test_a_minimal_hand_written_document_imports() -> None:
    # No metadata, no defaults — the least a human must write.
    yaml_text = """
    name: mini
    initial: Ask name
    states:
      - type: DATA_COLLECTION
        title: Ask name
        requires:
          - field: name
    """
    result = from_yaml(yaml_text)
    assert result.is_success
    assert result.value.initial_id == "ask-name"


def test_malformed_json_fails_without_raising() -> None:
    result = from_json("{ not valid json")
    assert result.is_failure and result.error is ErrorType.VALIDATION_ERROR


def test_a_missing_required_key_is_reported() -> None:
    result = from_json('{"name": "x"}')
    assert result.is_failure
    assert "initial" in str(result.error_details) and "states" in str(result.error_details)


def test_an_unknown_state_type_fails_cleanly() -> None:
    result = from_json('{"name": "x", "initial": "y", "states": [{"type": "NOPE", "title": "y"}]}')
    assert result.is_failure and result.error is ErrorType.VALIDATION_ERROR


def test_a_graph_error_propagates_as_a_failure() -> None:
    document = {
        "name": "x",
        "initial": "Ask name",
        "states": [{"type": "DATA_COLLECTION", "title": "Ask name", "requires": [{"field": "n"}]}],
        "transitions": [{"source_id": "ask-name", "target_id": "ghost"}],
    }
    assert import_from_dict(document).error is ErrorType.NOT_FOUND


@pytest.mark.parametrize("suffix", [".json", ".yaml", ".yml"])
def test_file_round_trip_by_extension(tmp_path: Path, suffix: str) -> None:
    workflow = _workflow()
    path = tmp_path / f"workflow{suffix}"
    export_to_file(workflow, path)
    assert import_from_file(path).value == workflow


def test_unsupported_extension_is_handled_on_both_sides(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        export_to_file(_workflow(), tmp_path / "workflow.toml")
    assert import_from_file(tmp_path / "workflow.toml").is_failure


def test_a_missing_file_fails_with_not_found(tmp_path: Path) -> None:
    result = import_from_file(tmp_path / "does-not-exist.json")
    assert result.is_failure and result.error is ErrorType.NOT_FOUND
