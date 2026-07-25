"""Converters between a workflow and a text document.

Each format is one small strategy — ``IDocumentConverter`` — with two methods:

* ``to_document``   — workflow -> text document
* ``from_document`` — text document -> workflow (never raises; returns a Result)

The shared workflow <-> dict logic lives in ``document.py``; a converter just
wraps it with the text encoding for its format.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from ..definition.workflow import Workflow
from ..result import ErrorType, Result
from .document import export_to_dict, import_from_dict


class IDocumentConverter(ABC):
    """Converts a workflow to and from one text format."""

    @abstractmethod
    def to_document(self, workflow: Workflow) -> str:
        """Serialize a workflow to a text document."""

    @abstractmethod
    def from_document(self, text: str) -> Result[Workflow, str]:
        """Parse a text document into a workflow. Never raises — returns a Result."""


class JsonConverter(IDocumentConverter):
    """Workflow <-> JSON (standard library only)."""

    def to_document(self, workflow: Workflow) -> str:
        return json.dumps(export_to_dict(workflow), indent=2, ensure_ascii=False) + "\n"

    def from_document(self, text: str) -> Result[Workflow, str]:
        try:
            document = json.loads(text)
        except json.JSONDecodeError as error:
            return Result.fail(ErrorType.VALIDATION_ERROR, f"invalid JSON: {error}")
        if not isinstance(document, dict):
            return Result.fail(ErrorType.VALIDATION_ERROR, "a workflow JSON must be an object")
        return import_from_dict(document)


class YamlConverter(IDocumentConverter):
    """Workflow <-> YAML (needs the optional PyYAML dependency)."""

    def to_document(self, workflow: Workflow) -> str:
        yaml = _require_pyyaml()
        text: str = yaml.safe_dump(export_to_dict(workflow), sort_keys=False, allow_unicode=True)
        return text

    def from_document(self, text: str) -> Result[Workflow, str]:
        yaml = _require_pyyaml()
        try:
            document = yaml.safe_load(text)
        except Exception as error:  # PyYAML raises yaml.YAMLError; broad for the lazy import
            return Result.fail(ErrorType.VALIDATION_ERROR, f"invalid YAML: {error}")
        if not isinstance(document, dict):
            return Result.fail(ErrorType.VALIDATION_ERROR, "a workflow YAML must be a mapping")
        return import_from_dict(document)


def _require_pyyaml() -> Any:
    """Import PyYAML, with a clear message if the optional extra is not installed."""
    try:
        import yaml
    except ImportError as error:
        raise ImportError(
            "YAML support needs PyYAML. Install it with: pip install 'markov-protocols[yaml]'"
        ) from error
    return yaml
