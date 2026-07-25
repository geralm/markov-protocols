"""conditions: the deterministic boolean core.

The load-bearing properties: absent data never asserts anything and never raises;
combinators obey boolean algebra; and a condition survives JSON round-trip (so a
workflow can be persisted).
"""

from pydantic import TypeAdapter

from markov_protocols import (
    All,
    Any,
    Condition,
    Eq,
    Exists,
    Gt,
    Gte,
    In,
    Lt,
    Ne,
    Not,
    Regex,
    evaluate,
)


def test_predicate_over_missing_field_is_false_and_never_raises() -> None:
    empty: dict[str, object] = {}
    leaves = [
        Exists(field="x"),
        Eq(field="x", value=1),
        Ne(field="x", value=1),
        In(field="x", value=[1]),
        Regex(field="x", value=".*"),
        Gt(field="x", value=1),
        Gte(field="x", value=1),
        Lt(field="x", value=1),
    ]
    for leaf in leaves:
        assert evaluate(leaf, empty) is False


def test_exists_requires_present_and_non_null() -> None:
    assert evaluate(Exists(field="x"), {"x": 0}) is True  # falsy-but-present counts
    assert evaluate(Exists(field="x"), {"x": None}) is False


def test_compare_boundaries_are_correct() -> None:
    assert evaluate(Gte(field="n", value=10), {"n": 10}) is True
    assert evaluate(Gt(field="n", value=10), {"n": 10}) is False
    assert evaluate(Lt(field="n", value=10), {"n": 9}) is True


def test_compare_on_incomparable_types_is_false_not_error() -> None:
    assert evaluate(Gt(field="n", value=10), {"n": "abc"}) is False


def test_regex_is_search_and_only_matches_strings() -> None:
    assert evaluate(Regex(field="email", value="@"), {"email": "a@b"}) is True
    assert evaluate(Regex(field="email", value="@"), {"email": "ab"}) is False
    assert evaluate(Regex(field="email", value="@"), {"email": 123}) is False


def test_combinator_identities_and_negation() -> None:
    assert evaluate(All(of=[]), {}) is True  # vacuous truth
    assert evaluate(Any(of=[]), {}) is False
    assert evaluate(Not(of=Exists(field="x")), {}) is True  # the one way to assert absence


def test_nested_combinators_branch_like_the_workflow() -> None:
    intent_is_known = Any(of=[Eq(field="intent", value="buy"), Eq(field="intent", value="support")])
    cond = All(of=[Exists(field="email"), intent_is_known])
    assert evaluate(cond, {"email": "a", "intent": "buy"}) is True
    assert evaluate(cond, {"email": "a", "intent": "other"}) is False


def test_condition_survives_json_round_trip() -> None:
    adapter: TypeAdapter[Condition] = TypeAdapter(Condition)
    cond = All(of=[Exists(field="email"), Not(of=Eq(field="intent", value="spam"))])
    assert adapter.validate_python(adapter.dump_python(cond)) == cond
