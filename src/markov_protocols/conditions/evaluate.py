"""Pure evaluation of a ``Condition`` against collected data.

The evaluator is a dispatch table: ``op`` → a tiny pure function. Two invariants
hold for every leaf:

* A condition over a **missing** field is ``False`` — never an error. Absent data
  can never assert anything, so a workflow can't be steered by data it doesn't have.
* Evaluation **never raises** on type mismatches (e.g. comparing a string to a
  number) — it returns ``False``. Determinism must not depend on data being clean.

Only ``Not`` inverts, so ``Not(Exists("x"))`` is ``True`` when ``x`` is absent — the
one intentional way to assert on absence.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any

from .models import (
    All,
    Condition,
    Eq,
    Exists,
    Gt,
    Gte,
    In,
    Lt,
    Lte,
    Ne,
    Not,
    Regex,
)
from .models import (
    Any as AnyCond,
)

_MISSING = object()


def evaluate(condition: Condition, data: Mapping[str, Any]) -> bool:
    """Return whether ``condition`` holds for ``data``."""
    return _DISPATCH[type(condition)](condition, data)


def condition_fields(condition: Condition) -> set[str]:
    """Every Blackboard field name a condition tree references.

    Used to report which data a state is still waiting on: the absent members of
    this set are its missing fields.
    """
    if isinstance(condition, All | AnyCond):
        if not condition.of:
            return set()
        return set().union(*(condition_fields(sub) for sub in condition.of))
    if isinstance(condition, Not):
        return condition_fields(condition.of)
    return {condition.field}


def _get(data: Mapping[str, Any], field: str) -> Any:
    return data.get(field, _MISSING)


def _exists(c: Exists, data: Mapping[str, Any]) -> bool:
    value = _get(data, c.field)
    return value is not _MISSING and value is not None


def _eq(c: Eq, data: Mapping[str, Any]) -> bool:
    value = _get(data, c.field)
    return value is not _MISSING and value == c.value


def _ne(c: Ne, data: Mapping[str, Any]) -> bool:
    value = _get(data, c.field)
    return value is not _MISSING and value != c.value


def _in(c: In, data: Mapping[str, Any]) -> bool:
    value = _get(data, c.field)
    return value is not _MISSING and value in c.value


def _regex(c: Regex, data: Mapping[str, Any]) -> bool:
    value = _get(data, c.field)
    return isinstance(value, str) and re.search(c.value, value) is not None


def _compare(op: Callable[[Any, Any], bool]) -> Callable[[Any, Mapping[str, Any]], bool]:
    def run(c: Any, data: Mapping[str, Any]) -> bool:
        value = _get(data, c.field)
        if value is _MISSING:
            return False
        try:
            return op(value, c.value)
        except TypeError:
            return False

    return run


def _all(c: All, data: Mapping[str, Any]) -> bool:
    return all(evaluate(sub, data) for sub in c.of)


def _any(c: AnyCond, data: Mapping[str, Any]) -> bool:
    return any(evaluate(sub, data) for sub in c.of)


def _not(c: Not, data: Mapping[str, Any]) -> bool:
    return not evaluate(c.of, data)


_DISPATCH: dict[type, Callable[[Any, Mapping[str, Any]], bool]] = {
    Exists: _exists,
    Eq: _eq,
    Ne: _ne,
    In: _in,
    Regex: _regex,
    Gt: _compare(lambda a, b: a > b),
    Gte: _compare(lambda a, b: a >= b),
    Lt: _compare(lambda a, b: a < b),
    Lte: _compare(lambda a, b: a <= b),
    All: _all,
    AnyCond: _any,
    Not: _not,
}
