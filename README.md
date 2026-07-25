# markov-protocols

A Finite State Machine capable of modeling workflows to provide guidance to an AI agent with determinism.

A standalone Python module providing the state-machine mechanism, meant to be reused across other Python projects.

## Status

Slices 1–3 complete — the engine is functionally whole:

- **Definition** — conditions, references, metadata, the `State` interface with three concrete state
  types, transitions, the registry, and `Workflow.compile()`.
- **Runtime** — `Blackboard`, the `Event` history, `Directive` materialization, and
  `Session.start/update` with the write + fast-forward passes.
- **Integrity** — a correction (`ValueChanged`) reopens the states that depend on it, strict-rewinds
  to the earliest one, clears reopened actions' outputs so they re-run, and flags `had_executed`
  for host compensation. All derived from `history` — no parallel bookkeeping.

See [`docs/DESIGN.md`](docs/DESIGN.md) for the full architecture and build plan.

## Development

Managed with [uv](https://docs.astral.sh/uv/).

```bash
uv sync            # create the environment and install dev tools
uv run pytest      # run the test suite
uv run ruff check  # lint
uv run mypy        # type-check
```

## Layout

```
src/markov_protocols/
    __init__.py        # curated public API
    result.py          # Result[T, E] / ErrorType — the error-handling pattern
    base.py            # StrictModel / StrictOpenModel
    slug.py            # deterministic title -> id
    conditions/        # the typed boolean vocabulary + pure evaluator
    references.py      # Ref + resolve + referenced_fields
    definition/        # metadata, State interface + concrete states, Transition,
                       #   registry, Workflow.compile()
    runtime/           # Blackboard, Event history, Session + update() pipeline
tests/                 # one property-focused module per unit
```

## Conventions

- Operations return a `Result[T, E]` instead of raising exceptions.
- Target Python 3.13+.
