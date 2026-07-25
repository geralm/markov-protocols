"""blackboard: writes must diff correctly and stay quiet on no-ops."""

from markov_protocols import Blackboard, ValueChanged, ValueSet


def test_writing_a_new_field_emits_value_set() -> None:
    board = Blackboard()
    events = board.write({"email": "a@b"})
    assert events == [ValueSet(field="email", value="a@b")]
    assert board["email"] == "a@b"


def test_overwriting_with_a_different_value_emits_value_changed() -> None:
    board = Blackboard({"email": "old@b"})
    events = board.write({"email": "new@b"})
    assert events == [ValueChanged(field="email", old="old@b", new="new@b")]


def test_writing_the_same_value_emits_nothing() -> None:
    board = Blackboard({"email": "a@b"})
    assert board.write({"email": "a@b"}) == []


def test_blackboard_reads_like_a_mapping() -> None:
    board = Blackboard({"email": "a@b"})
    assert "email" in board
    assert board.get("missing") is None
    assert board.to_dict() == {"email": "a@b"}
