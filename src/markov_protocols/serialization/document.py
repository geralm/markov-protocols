"""The format-agnostic core: a workflow <-> a plain dict.

This is the one place that knows a workflow's shape. Every text format (JSON,
YAML, ...) is just a thin wrapper around this, so the workflow logic is never
duplicated per format.

The dict is intentionally friendly to hand-write:

    name: real-estate-intake
    initial: Collect email          # a title or a slug; both resolve the same
    states:
      - type: DATA_COLLECTION
        title: Collect email
        requires:
          - field: email
    transitions:
      - source_id: collect-email
        target_id: send-confirmation

Importing routes through ``Workflow.compile()``, so it gets full graph validation
and returns a ``Result`` — a bad dict is a friendly failure, never a crash.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from ..definition.workflow import Workflow
from ..result import ErrorType, Result

_REQUIRED_KEYS = ("name", "initial", "states")


def export_to_dict(workflow: Workflow) -> dict[str, Any]:
    """Convert a workflow into a plain, JSON/YAML-ready dict."""
    dumped = workflow.model_dump(mode="json")
    # Present the friendly, compile-compatible shape: `initial` (not `initial_id`),
    # and a stable key order that reads well when written to a file.
    return {
        "name": dumped["name"],
        "initial": dumped["initial_id"],
        "states": dumped["states"],
        "transitions": dumped["transitions"],
    }


def import_from_dict(document: Mapping[str, Any]) -> Result[Workflow, str]:
    """Build a validated workflow from a plain dict.

    Fails (without raising) when a required key is absent, a state type is unknown,
    a field is malformed, or the graph itself is invalid.
    """
    missing = [key for key in _REQUIRED_KEYS if key not in document]
    if missing:
        return Result.fail(ErrorType.VALIDATION_ERROR, f"document is missing keys: {missing}")

    try:
        return Workflow.compile(
            name=document["name"],
            initial=document["initial"],
            states=document.get("states", []),
            transitions=document.get("transitions", []),
        )
    except (ValueError, ValidationError) as error:
        # Turn construction problems (unknown state type, bad field) into a clean
        # failure so hand-authored documents report mistakes instead of crashing.
        return Result.fail(ErrorType.VALIDATION_ERROR, f"invalid workflow document: {error}")
