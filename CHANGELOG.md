# Changelog

## 0.5.0

Adds workflow visualization, and makes conditions render themselves.

### Added
- **`export_graph(workflow, format="mermaid")`** (plus `to_mermaid` / `to_ascii`) —
  a flowchart of the compiled workflow: each state's title + type, the transitions,
  and the guard on each branch. Mermaid (LangGraph-style) or an ASCII outline.
- **`Condition` now implements `Renderable`** — every condition renders itself
  (`to_llm_extended` / `to_markdown`, e.g. `"intent == buy"`). This removes the
  type-switch that would otherwise live in the visualizer, and lets guards be
  printed in prompts too.

### Changed
- `Workflow.to_llm_extended()` now shows the actual guard condition on a
  transition (e.g. `[intent == buy]`) instead of a generic `(conditional)`.

## 0.4.0

Adds a workflow **field namespace** — reference validation and Blackboard bounding.

### Added
- **`Workflow.external_fields`** — declare fields the host provides that no state
  collects (e.g. a pre-seeded id). Together with every state's `requires`, they form
  the workflow's field namespace, exposed (derived) as **`Workflow.fields`**.
- **Compile-time reference check** — a `Ref` to a field outside the namespace now
  fails `compile()` with a clear message, instead of deadlocking at runtime.
- **Blackboard bounding** — `Session.update()` stores only known fields; unknown keys
  are dropped (so the Blackboard can't be flooded) and reported in the new
  **`UpdateResult.ignored_fields`**.

### Notes
- No ordering ("used before collected") check: a field may legitimately be volunteered
  early, so that would false-positive. Runtime already reports a genuinely missing
  reference via `directive.ready == False` / `directive.missing`.
- Migration: if a workflow `Ref`s a host-provided field that no state collects, add it
  to `external_fields`.

## 0.3.0

Unifies how every state declares the fields it waits on, and adds optional
requirements, field types, and Pydantic-schema generation.

### Added
- **Optional requirements** — `Requirement.required: bool = True`. An optional
  requirement (`required=False`) is captured if provided but never blocks a step.
- **Field types** — `Requirement.type: ValueType` (`STRING` default, plus
  `INTEGER`, `NUMBER`, `BOOLEAN`, `ARRAY`).
- **`State.to_pydantic_model()`** — builds a Pydantic model from a state's
  `requires` (required vs nullable, `options` → enum, `Regex` → pattern) for LLM
  structured output and for validating extracted results. Lives on the base
  `State`, so it works for every state type.
- **`State.expected_fields()`** — the requirements a state expects (uniform).
- `field_options()` now reports each field's `required` flag and `type`.

### Changed (breaking)
- **`ActionExecuteState` and `HumanHandoffState` now use `requires`** instead of
  `result_field` / `resolution_field`. Every state declares
  `requires: list[Requirement]`; completion, blockers, schema, and rendering are
  now shared base logic driven by it.

  Migration:
  ```python
  # before (0.2.x)
  ActionExecuteState(title="Send", payload={...}, result_field="sent")
  HumanHandoffState(title="Escalate", resolution_field="resolved")

  # after (0.3.0)
  ActionExecuteState(title="Send", payload={...},
                     requires=[Requirement(field="sent", type=ValueType.BOOLEAN)])
  HumanHandoffState(title="Escalate", requires=[Requirement(field="resolved")])
  ```
  In JSON/YAML documents, replace `result_field: x` / `resolution_field: x` with
  a `requires:` list.

## 0.2.1
- README turned into a full PyPI usage guide.

## 0.2.0
- Blockers (`MISSING`/`INVALID`/`AWAITING_*`), requirement `options` +
  descriptions, and the `Renderable` factual-text layer (`to_llm_extended`,
  `to_markdown`).

## 0.1.0
- Initial release: deterministic FSM (definition, runtime, integrity),
  JSON/YAML serialization.
