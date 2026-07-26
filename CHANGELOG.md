# Changelog

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
