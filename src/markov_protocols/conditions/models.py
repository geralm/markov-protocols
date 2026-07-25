"""The ``Condition`` discriminated union.

Each condition is a small immutable value object tagged by ``op``. Leaf conditions
test one field; combinators (``all``/``any``/``not``) nest other conditions. The
union is discriminated on ``op`` so it round-trips cleanly through JSON.
"""

from __future__ import annotations

from typing import Annotated, Literal
from typing import Any as AnyType

from pydantic import Field

from ..base import StrictModel


class Exists(StrictModel):
    """True when ``field`` is present and not null."""

    op: Literal["exists"] = "exists"
    field: str


class Eq(StrictModel):
    """True when ``field`` exists and equals ``value``."""

    op: Literal["eq"] = "eq"
    field: str
    value: AnyType


class Ne(StrictModel):
    """True when ``field`` exists and does not equal ``value`` (missing → False)."""

    op: Literal["ne"] = "ne"
    field: str
    value: AnyType


class In(StrictModel):
    """True when ``field`` exists and its value is one of ``value``."""

    op: Literal["in"] = "in"
    field: str
    value: list[AnyType]


class Regex(StrictModel):
    """True when ``field`` is a string that ``value`` (a regex) finds a match in."""

    op: Literal["regex"] = "regex"
    field: str
    value: str


class Gt(StrictModel):
    op: Literal["gt"] = "gt"
    field: str
    value: AnyType


class Gte(StrictModel):
    op: Literal["gte"] = "gte"
    field: str
    value: AnyType


class Lt(StrictModel):
    op: Literal["lt"] = "lt"
    field: str
    value: AnyType


class Lte(StrictModel):
    op: Literal["lte"] = "lte"
    field: str
    value: AnyType


class All(StrictModel):
    """True when every nested condition is true (vacuously true when empty)."""

    op: Literal["all"] = "all"
    of: list[Condition]


class Any(StrictModel):
    """True when at least one nested condition is true (false when empty)."""

    op: Literal["any"] = "any"
    of: list[Condition]


class Not(StrictModel):
    """The negation of a nested condition."""

    op: Literal["not"] = "not"
    of: Condition


Condition = Annotated[
    Exists | Eq | Ne | In | Regex | Gt | Gte | Lt | Lte | All | Any | Not,
    Field(discriminator="op"),
]
"""Any boolean rule over the Blackboard."""

# Resolve the forward references inside the recursive combinators.
All.model_rebuild()
Any.model_rebuild()
Not.model_rebuild()
