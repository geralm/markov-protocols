"""Visualize a compiled workflow as a flowchart — Mermaid or ASCII.

Facts only, like the rest of the rendering surface: each state's title and type,
the transitions, and the guard on each branch (rendered by the condition itself).
This module is an independent sibling of ``serialization`` — it only reads the
definition models, imports nothing from serialization, and is imported by neither.

    export_graph(workflow)            # Mermaid (default)
    export_graph(workflow, "ascii")   # indented ASCII outline
"""

from __future__ import annotations

import re

from .definition.state import State
from .definition.transition import Transition
from .definition.workflow import Workflow

_NON_ID = re.compile(r"[^0-9a-zA-Z_]")


def export_graph(workflow: Workflow, format: str = "mermaid") -> str:
    """Render the workflow as a flowchart. ``format`` is ``"mermaid"`` or ``"ascii"``."""
    if format == "mermaid":
        return to_mermaid(workflow)
    if format == "ascii":
        return to_ascii(workflow)
    raise ValueError(f"unknown format {format!r}; use 'mermaid' or 'ascii'")


def to_mermaid(workflow: Workflow) -> str:
    """A Mermaid ``flowchart TD`` — nodes are ``title`` + type, edges carry guards."""
    lines = ["flowchart TD", f"    __start__([Start]) --> {_node(workflow.initial_id)}"]

    for state in workflow.states:
        lines.append(f'    {_node(state.id)}["{state.title}<br/><i>{_type_of(state)}</i>"]')

    for transition in workflow.transitions:
        lines.append(f"    {_edge(transition)}")

    for state in workflow.states:
        if not workflow.outgoing(state.id):  # a terminal step
            lines.append(f"    {_node(state.id)} --> __end__([End])")

    return "\n".join(lines)


def to_ascii(workflow: Workflow) -> str:
    """An indented outline: each state, its type, and its guarded out-edges."""
    lines = [f"Workflow: {workflow.name}"]
    for state in workflow.states:
        lines.append(f"[{_type_of(state)}] {state.title}{_role(workflow, state)}")
        for transition in workflow.outgoing(state.id):
            guard = f"  [{transition.guard.to_llm_extended()}]" if transition.guard else ""
            lines.append(f"    -> {transition.target_id}{guard}")
    return "\n".join(lines)


# --- internals ---------------------------------------------------------------


def _node(state_id: str) -> str:
    """A Mermaid-safe node id (slug hyphens -> underscores)."""
    return _NON_ID.sub("_", state_id)


def _type_of(state: State) -> str:
    """The state's ``type`` tag (e.g. DATA_COLLECTION), or its class name."""
    field = type(state).model_fields.get("type")
    if field is not None and field.default is not None:
        return str(field.default)
    return type(state).__name__


def _role(workflow: Workflow, state: State) -> str:
    if state.id == workflow.initial_id:
        return "  (initial)"
    if not workflow.outgoing(state.id):
        return "  (terminal)"
    return ""


def _edge(transition: Transition) -> str:
    source, target = _node(transition.source_id), _node(transition.target_id)
    if transition.guard is None:
        return f"{source} --> {target}"
    label = transition.guard.to_llm_extended().replace('"', "'")
    return f'{source} -->|"{label}"| {target}'
