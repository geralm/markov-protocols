"""The Blackboard: the shared, deterministic record of collected values.

It is a plain ``Mapping``, so ``Condition`` evaluation and ``Ref`` resolution read
it directly. Writing diffs against the current contents so the machine learns
whether each field is new (``ValueSet``) or a correction (``ValueChanged``) — the
signal Slice 3 uses to reopen states.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

from .events import Event, ValueChanged, ValueSet


class Blackboard(Mapping[str, Any]):
    """A mapping of field → collected value for one session."""

    def __init__(self, data: Mapping[str, Any] | None = None) -> None:
        self._data: dict[str, Any] = dict(data) if data else {}

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def to_dict(self) -> dict[str, Any]:
        """A copy of the current contents."""
        return dict(self._data)

    def remove(self, field: str) -> None:
        """Drop a field if present. Used to clear a reopened action's stale output."""
        self._data.pop(field, None)

    def write(self, values: Mapping[str, Any]) -> list[Event]:
        """Apply ``values``, returning one event per field that actually changed.

        Writing a field its current value is a no-op (no event) — so re-confirming
        unchanged data never produces churn.
        """
        events: list[Event] = []
        for field, value in values.items():
            if field not in self._data:
                self._data[field] = value
                events.append(ValueSet(field=field, value=value))
            elif self._data[field] != value:
                old = self._data[field]
                self._data[field] = value
                events.append(ValueChanged(field=field, old=old, new=value))
        return events
