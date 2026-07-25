"""Shared Pydantic bases used across every layer.

``StrictModel`` is the default: it rejects unknown fields and revalidates on
assignment, so a malformed definition can never silently exist. ``StrictOpenModel``
relaxes only the "unknown fields" rule — used for metadata, where we validate the
*shape* we rely on but let business policy attach anything else.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Reject unknown fields; validate on every assignment."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class StrictOpenModel(BaseModel):
    """Validate declared fields, but allow extra ones (extensible metadata)."""

    model_config = ConfigDict(extra="allow", validate_assignment=True)
