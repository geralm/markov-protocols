"""references: value binding must resolve fully or fail loudly — never partially."""

from markov_protocols import ErrorType, Ref, referenced_fields, resolve


def test_resolve_replaces_refs_anywhere_and_leaves_literals() -> None:
    payload = {
        "url": "http://x",
        "body": {"to": Ref(field="email"), "items": [Ref(field="name"), "lit"]},
    }
    result = resolve(payload, {"email": "a@b", "name": "Pedro"})
    assert result.is_success
    assert result.value == {"url": "http://x", "body": {"to": "a@b", "items": ["Pedro", "lit"]}}


def test_resolve_missing_field_fails_loudly_naming_the_field() -> None:
    result = resolve({"to": Ref(field="email")}, {})
    assert result.is_failure
    assert result.error is ErrorType.NOT_FOUND
    assert result.error_details == ["email"]


def test_resolve_is_atomic_no_partial_payload_on_failure() -> None:
    # One field present, one missing: the whole resolution fails, nothing is emitted.
    result = resolve({"a": Ref(field="present"), "b": Ref(field="missing")}, {"present": 1})
    assert result.is_failure
    assert result.value is None


def test_referenced_fields_is_the_consumes_set() -> None:
    payload = {"to": Ref(field="email"), "cc": [Ref(field="manager")], "note": "literal"}
    assert referenced_fields(payload) == {"email", "manager"}


def test_referenced_fields_recognizes_serialized_ref_dicts() -> None:
    # A Ref that has been dumped to JSON and back is still counted.
    assert referenced_fields({"to": {"type": "ref", "field": "email"}}) == {"email"}
