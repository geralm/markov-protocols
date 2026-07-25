"""Conditions: a small, closed, typed boolean vocabulary over the Blackboard.

A ``Condition`` reads collected data and returns a ``bool`` — the only way the
machine asks a yes/no question. The vocabulary is deliberately closed (not an open
expression language): it validates at authoring time, serializes to JSON, and is
safe to evaluate with no ``eval``.
"""

from __future__ import annotations

from .evaluate import condition_fields, evaluate
from .models import (
    All,
    Any,
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

__all__ = [
    "All",
    "Any",
    "Condition",
    "Eq",
    "Exists",
    "Gt",
    "Gte",
    "In",
    "Lt",
    "Lte",
    "Ne",
    "Not",
    "Regex",
    "condition_fields",
    "evaluate",
]
