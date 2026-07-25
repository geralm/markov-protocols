"""Import and export workflows as JSON or YAML.

    from markov_protocols import to_json, from_json, to_yaml, from_yaml
    text   = to_json(workflow)
    result = from_json(text)        # -> Result[Workflow, str]

Structure: one ``IDocumentConverter`` strategy per format (``converter.py``), a
shared workflow <-> dict core (``document.py``), and the thin facade below that
names each direction. Add a format by writing a converter and two facade functions.
"""

from __future__ import annotations

from pathlib import Path

from ..definition.workflow import Workflow
from ..result import ErrorType, Result
from .converter import IDocumentConverter, JsonConverter, YamlConverter
from .document import export_to_dict, import_from_dict

__all__ = [
    "IDocumentConverter",
    "export_to_dict",
    "export_to_file",
    "from_json",
    "from_yaml",
    "import_from_dict",
    "import_from_file",
    "to_json",
    "to_yaml",
]

_JSON = JsonConverter()
_YAML = YamlConverter()

# Which converter handles which file extension.
_BY_EXTENSION: dict[str, IDocumentConverter] = {
    ".json": _JSON,
    ".yaml": _YAML,
    ".yml": _YAML,
}


def to_json(workflow: Workflow) -> str:
    """Serialize a workflow to a JSON string."""
    return _JSON.to_document(workflow)


def from_json(text: str) -> Result[Workflow, str]:
    """Build a workflow from a JSON string. Never raises — returns a Result."""
    return _JSON.from_document(text)


def to_yaml(workflow: Workflow) -> str:
    """Serialize a workflow to a YAML string."""
    return _YAML.to_document(workflow)


def from_yaml(text: str) -> Result[Workflow, str]:
    """Build a workflow from a YAML string. Never raises — returns a Result."""
    return _YAML.from_document(text)


def export_to_file(workflow: Workflow, path: str | Path) -> None:
    """Write a workflow to a file, choosing the format from its extension."""
    path = Path(path)
    converter = _BY_EXTENSION.get(path.suffix.lower())
    if converter is None:
        raise ValueError(f"unsupported extension {path.suffix!r}; use .json, .yaml, or .yml")
    path.write_text(converter.to_document(workflow))


def import_from_file(path: str | Path) -> Result[Workflow, str]:
    """Read a workflow from a .json/.yaml/.yml file. Never raises — returns a Result."""
    path = Path(path)
    converter = _BY_EXTENSION.get(path.suffix.lower())
    if converter is None:
        return Result.fail(ErrorType.VALIDATION_ERROR, f"unsupported extension {path.suffix!r}")
    try:
        text = path.read_text()
    except OSError as error:
        return Result.fail(ErrorType.NOT_FOUND, f"could not read {path}: {error}")
    return converter.from_document(text)
