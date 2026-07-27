"""The ``Condition`` discriminated union.

Each condition is a small immutable value object tagged by ``op``. Leaf conditions
test one field; combinators (``all``/``any``/``not``) nest other conditions. The
union is discriminated on ``op`` so it round-trips cleanly through JSON.

Every condition is ``Renderable``: it renders *itself* to a short factual string
(``to_llm_extended`` / ``to_markdown``) — used for prompts and for guard labels in
diagrams. Because each type renders itself, no code anywhere switches on ``op``.
"""

from __future__ import annotations

from typing import Annotated, Literal
from typing import Any as AnyType

from pydantic import Field

from ..base import StrictModel
from ..renderable import Renderable


class Exists(StrictModel, Renderable):
    """True when ``field`` is present and not null."""

    op: Literal["exists"] = "exists"
    field: str

    def to_llm_extended(self) -> str:
        return f"{self.field} exists"


class Eq(StrictModel, Renderable):
    """True when ``field`` exists and equals ``value``."""

    op: Literal["eq"] = "eq"
    field: str
    value: AnyType

    def to_llm_extended(self) -> str:
        return f"{self.field} == {self.value}"


class Ne(StrictModel, Renderable):
    """True when ``field`` exists and does not equal ``value`` (missing → False)."""

    op: Literal["ne"] = "ne"
    field: str
    value: AnyType

    def to_llm_extended(self) -> str:
        return f"{self.field} != {self.value}"


class In(StrictModel, Renderable):
    """True when ``field`` exists and its value is one of ``value``."""

    op: Literal["in"] = "in"
    field: str
    value: list[AnyType]

    def to_llm_extended(self) -> str:
        return f"{self.field} in {self.value}"


class Regex(StrictModel, Renderable):
    """True when ``field`` is a string that ``value`` (a regex) finds a match in."""

    op: Literal["regex"] = "regex"
    field: str
    value: str

    def to_llm_extended(self) -> str:
        return f"{self.field} matches {self.value}"


class Gt(StrictModel, Renderable):
    op: Literal["gt"] = "gt"
    field: str
    value: AnyType

    def to_llm_extended(self) -> str:
        return f"{self.field} > {self.value}"


class Gte(StrictModel, Renderable):
    op: Literal["gte"] = "gte"
    field: str
    value: AnyType

    def to_llm_extended(self) -> str:
        return f"{self.field} >= {self.value}"


class Lt(StrictModel, Renderable):
    op: Literal["lt"] = "lt"
    field: str
    value: AnyType

    def to_llm_extended(self) -> str:
        return f"{self.field} < {self.value}"


class Lte(StrictModel, Renderable):
    op: Literal["lte"] = "lte"
    field: str
    value: AnyType

    def to_llm_extended(self) -> str:
        return f"{self.field} <= {self.value}"


class All(StrictModel, Renderable):
    """True when every nested condition is true (vacuously true when empty)."""

    op: Literal["all"] = "all"
    of: list[Condition]

    def to_llm_extended(self) -> str:
        return " and ".join(sub.to_llm_extended() for sub in self.of)


class Any(StrictModel, Renderable):
    """True when at least one nested condition is true (false when empty)."""

    op: Literal["any"] = "any"
    of: list[Condition]

    def to_llm_extended(self) -> str:
        return " or ".join(sub.to_llm_extended() for sub in self.of)


class Not(StrictModel, Renderable):
    """The negation of a nested condition."""

    op: Literal["not"] = "not"
    of: Condition

    def to_llm_extended(self) -> str:
        return f"not ({self.of.to_llm_extended()})"


Condition = Annotated[
    Exists | Eq | Ne | In | Regex | Gt | Gte | Lt | Lte | All | Any | Not,
    Field(discriminator="op"),
]
"""Any boolean rule over the Blackboard."""

# Resolve the forward references inside the recursive combinators.
All.model_rebuild()
Any.model_rebuild()
Not.model_rebuild()
