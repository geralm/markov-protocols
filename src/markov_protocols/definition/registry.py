"""The state-type registry — how the definition layer stays open for extension.

Concrete state types register their ``type`` tag here. That lets a workflow (with
any mix of built-in or third-party states) round-trip through JSON: on load, each
state dict is dispatched to the class its ``type`` names. The engine itself never
consults this — it only ever talks to the ``State`` interface.
"""

from __future__ import annotations

from typing import Any

from .state import State
from .states import ActionExecuteState, DataCollectionState, HumanHandoffState


class StateRegistry:
    """Maps a state ``type`` tag to the class that implements it."""

    def __init__(self) -> None:
        self._by_type: dict[str, type[State]] = {}

    def register(self, state_type: type[State]) -> None:
        """Register a concrete state class. Rejects duplicate ``type`` tags."""
        tag = _type_tag(state_type)
        existing = self._by_type.get(tag)
        if existing is not None and existing is not state_type:
            raise ValueError(f"state type {tag!r} is already registered to {existing.__name__}")
        self._by_type[tag] = state_type

    def parse(self, value: Any) -> State:
        """Build a concrete ``State`` from an instance or its serialized dict form."""
        if isinstance(value, State):
            return value
        if not isinstance(value, dict) or "type" not in value:
            raise ValueError("cannot parse state: expected a State or a dict with a 'type' key")
        tag = value["type"]
        cls = self._by_type.get(tag)
        if cls is None:
            raise ValueError(f"unknown state type: {tag!r}")
        return cls.model_validate(value)


def _type_tag(state_type: type[State]) -> str:
    field = state_type.model_fields.get("type")
    if field is None or field.default is None:
        raise ValueError(f"{state_type.__name__} must declare a literal 'type' field")
    return str(field.default)


state_registry = StateRegistry()
state_registry.register(DataCollectionState)
state_registry.register(ActionExecuteState)
state_registry.register(HumanHandoffState)
