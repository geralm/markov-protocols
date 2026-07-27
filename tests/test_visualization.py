"""visualization: Mermaid / ASCII flowcharts, and conditions rendering themselves."""

import pytest

from markov_protocols import (
    All,
    DataCollectionState,
    Eq,
    Exists,
    In,
    Not,
    Requirement,
    Transition,
    Workflow,
    export_graph,
    to_ascii,
    to_mermaid,
)


def _workflow() -> Workflow:
    return Workflow.compile(
        name="triage",
        initial="Detect intent",
        states=[
            DataCollectionState(title="Detect intent", requires=[Requirement(field="intent")]),
            DataCollectionState(title="Sales", requires=[Requirement(field="budget")]),
            DataCollectionState(title="Support", requires=[Requirement(field="issue")]),
        ],
        transitions=[
            Transition(source_id="detect-intent", target_id="sales",
                       guard=Eq(field="intent", value="buy")),
            Transition(source_id="detect-intent", target_id="support",
                       guard=Eq(field="intent", value="support")),
        ],
    ).value


# --- conditions render themselves (no if/isinstance switch anywhere) ---------


def test_leaf_conditions_render_field_op_value() -> None:
    assert Eq(field="x", value=1).to_llm_extended() == "x == 1"
    assert Exists(field="x").to_llm_extended() == "x exists"
    assert In(field="x", value=["a", "b"]).to_llm_extended() == "x in ['a', 'b']"


def test_combinators_recurse_into_children() -> None:
    cond = All(of=[Exists(field="email"), Not(of=Eq(field="intent", value="spam"))])
    assert cond.to_llm_extended() == "email exists and not (intent == spam)"


def test_to_markdown_matches_to_llm_extended_for_conditions() -> None:
    cond = Eq(field="intent", value="buy")
    assert cond.to_markdown() == cond.to_llm_extended()


# --- mermaid -----------------------------------------------------------------


def test_mermaid_has_flowchart_header_and_start_end() -> None:
    diagram = to_mermaid(_workflow())
    assert diagram.startswith("flowchart TD")
    assert "__start__([Start]) --> detect_intent" in diagram
    assert "--> __end__([End])" in diagram  # terminal states point at end


def test_mermaid_nodes_carry_title_and_type() -> None:
    diagram = to_mermaid(_workflow())
    assert 'detect_intent["Detect intent<br/><i>DATA_COLLECTION</i>"]' in diagram


def test_mermaid_edges_carry_the_guard_condition() -> None:
    diagram = to_mermaid(_workflow())
    assert 'detect_intent -->|"intent == buy"| sales' in diagram
    assert 'detect_intent -->|"intent == support"| support' in diagram


# --- ascii -------------------------------------------------------------------


def test_ascii_shows_types_roles_and_guarded_edges() -> None:
    text = to_ascii(_workflow())
    assert "[DATA_COLLECTION] Detect intent  (initial)" in text
    assert "-> sales  [intent == buy]" in text
    assert "[DATA_COLLECTION] Sales  (terminal)" in text


# --- facade ------------------------------------------------------------------


def test_export_graph_dispatches_by_format() -> None:
    workflow = _workflow()
    assert export_graph(workflow, "mermaid") == to_mermaid(workflow)
    assert export_graph(workflow, "ascii") == to_ascii(workflow)
    assert export_graph(workflow) == to_mermaid(workflow)  # default


def test_export_graph_rejects_unknown_format() -> None:
    with pytest.raises(ValueError):
        export_graph(_workflow(), "svg")
