"""References and resolution.

A ``Ref`` is the only value-binding primitive: it names a Blackboard field to be
substituted into a payload (a webhook body, a notification, ...). ``resolve``
replaces every ``Ref`` in a payload with its value deterministically; if any
referenced field is absent it **fails loudly** — a payload is never handed over
half-resolved, so a side effect can't fire with a blank value.

``referenced_fields`` returns the set of Blackboard fields a payload references —
exactly what that payload *consumes*, and the same set the machine uses to decide
what to reopen when data changes.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from .base import StrictModel
from .result import ErrorType, Result


class Ref(StrictModel):
    """A reference to a Blackboard field, resolved when a payload is built."""

    type: Literal["ref"] = "ref"
    field: str


def as_ref(value: Any) -> Ref | None:
    """Return a ``Ref`` if ``value`` is one (instance or its serialized dict form)."""
    if isinstance(value, Ref):
        return value
    if isinstance(value, dict) and value.get("type") == "ref" and "field" in value:
        return Ref(field=value["field"])
    return None


def normalize_refs(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a payload dict with every ref-shaped dict replaced by a ``Ref``.

    Applied when a state is built so an authored ``Ref`` and one rehydrated from
    JSON share one canonical form — the two compare equal.
    """
    return {k: _normalize(v) for k, v in payload.items()}


def _normalize(value: Any) -> Any:
    ref = as_ref(value)
    if ref is not None:
        return ref
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    return value


def referenced_fields(payload: Any) -> set[str]:
    """Return every Blackboard field name referenced anywhere within ``payload``."""
    ref = as_ref(payload)
    if ref is not None:
        return {ref.field}
    if isinstance(payload, dict):
        return set().union(*(referenced_fields(v) for v in payload.values())) if payload else set()
    if isinstance(payload, (list, tuple)):
        return set().union(*(referenced_fields(v) for v in payload)) if payload else set()
    return set()


def resolve(payload: Any, data: Mapping[str, Any]) -> Result[Any, list[str]]:
    """Return a copy of ``payload`` with every ``Ref`` replaced by its value.

    Reads any mapping (including a ``Blackboard``). Fails with the list of missing
    fields if any reference cannot be resolved; on failure no partial payload is
    produced.
    """
    missing: list[str] = []
    resolved = _resolve(payload, data, missing)
    if missing:
        return Result.fail(ErrorType.NOT_FOUND, sorted(set(missing)))
    return Result.ok(resolved)


def _resolve(payload: Any, data: Mapping[str, Any], missing: list[str]) -> Any:
    ref = as_ref(payload)
    if ref is not None:
        if ref.field not in data:
            missing.append(ref.field)
            return None
        return data[ref.field]
    if isinstance(payload, dict):
        return {k: _resolve(v, data, missing) for k, v in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [_resolve(v, data, missing) for v in payload]
    return payload
