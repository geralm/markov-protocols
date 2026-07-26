# markov-protocols

**A deterministic finite state machine for modeling workflows that guide AI agents.**

LLMs are stochastic. When a workflow must happen *reliably* — collect these fields, validate them,
call that action, handle a correction — prompting alone drifts and hallucinates. `markov-protocols`
is the **deterministic referee**: you model the workflow as a state machine, the agent reads the
current step for guidance and reports what it learned, and the machine decides — deterministically —
what happens next. It never calls an LLM, runs a tool, or performs I/O; your host does that.

- **Deterministic**: same definition + same collected data → same decision, every time.
- **Correction-aware**: if the customer changes their mind, the machine rewinds and re-runs only
  what's affected (and tells you if a side effect must be compensated).
- **Typed & serializable**: author in Python or as JSON/YAML; validated, `mypy`-clean, `py.typed`.

## Install

```bash
pip install markov-protocols
pip install "markov-protocols[yaml]"   # optional: YAML import/export
```

Requires Python 3.13+.

## Quickstart

```python
from markov_protocols import (
    Workflow, DataCollectionState, ActionExecuteState,
    Requirement, ValueType, Ref, Transition, Session,
)

# 1. Define the workflow (plain data).
workflow = Workflow.compile(
    name="intake",
    initial="Collect email",
    states=[
        DataCollectionState(
            title="Collect email",
            requires=[Requirement(field="email", description="the customer's email")],
        ),
        ActionExecuteState(
            title="Send confirmation",
            payload={"to": Ref(field="email")},   # a Ref, filled from collected data
            requires=[Requirement(field="confirmation_sent", type=ValueType.BOOLEAN)],  # its result
        ),
    ],
    transitions=[
        Transition(source_id="collect-email", target_id="send-confirmation"),
    ],
).value  # compile() returns a Result; .value is the validated Workflow

# 2. Run it. Feed in whatever your agent extracted from the conversation.
session = Session.start(workflow)

outcome = session.update({"email": "pedro@example.com"}).value
print(outcome.current_state.id)      # 'send-confirmation'  (advanced automatically)
print(outcome.directive.payload)     # {'to': 'pedro@example.com'}  (resolved, ready to run)

# 3. Your host runs the action and reports the result back.
session.update({"confirmation_sent": True})
print(session.is_finished)           # True
```

`update()` is the single input verb: it records the data, then **fast-forwards** through every step
the data already satisfies — so one call can advance several steps, or hold position when it can't.

## Your agent loop

The machine is the deterministic referee; your host owns everything stochastic or side-effectful:

```python
session = Session.start(workflow)
while not session.is_finished:
    values  = my_llm.extract(conversation, session.current_state)   # your LLM (stochastic)
    outcome = session.update(values).value                          # the machine (deterministic)

    directive = outcome.directive
    if directive and directive.ready:                               # a side effect to run
        result = my_host.run(directive.payload)                     # your webhook / function
        session.update({outcome.awaiting[0]: result})              # report it to the awaited field
```

## Guidance & validation

Constrain values with `options` (an enum with per-value descriptions) or any `Condition`. When a
step can't advance, `blockers` tells you *why* — and the convenience views split it apart:

```python
from markov_protocols import DataCollectionState, Requirement, Option, Workflow, Session

triage = Workflow.compile(
    name="triage",
    initial="Detect intent",
    states=[DataCollectionState(
        title="Detect intent",
        requires=[Requirement(
            field="intent",
            description="what the customer wants",
            options=[Option(value="buy", description="wants to purchase"),
                     Option(value="support", description="needs help")],
        )],
    )],
).value

outcome = Session.start(triage).update({"intent": "rent"}).value
print(outcome.missing_fields)          # []           — the field IS present...
print(outcome.invalid_fields)          # ['intent']   — ...but 'rent' isn't allowed
print(outcome.to_llm_extended())       # factual, prompt-ready text (no business prompts, facts only):
# Step: Detect intent
# - intent: what the customer wants (one of: buy (wants to purchase), support (needs help))
# Blocked by:
# - 'intent' is invalid: 'rent' is not allowed; choose one of: buy (wants to purchase), support (needs help)
```

Branch on a value with a transition **guard**: `Transition(source_id=..., target_id=..., guard=Eq(field="intent", value="buy"))`.

## Save & load (JSON / YAML)

```python
from markov_protocols import to_yaml, from_yaml, export_to_file, import_from_file

text   = to_yaml(workflow)            # -> YAML string
result = from_yaml(text)              # -> Result[Workflow]  (validated; a bad doc fails, never crashes)

export_to_file(workflow, "flow.json") # format from the extension (.json/.yaml/.yml)
loaded = import_from_file("flow.yaml")
```

A workflow document is easy to hand-author — `type` + `title` + the state's own fields:

```yaml
name: intake
initial: Collect email
states:
  - type: DATA_COLLECTION
    title: Collect email
    requires:
      - field: email
transitions: []
```

## Concepts

| Term | What it is |
|---|---|
| **Workflow** | the authored graph of states + transitions (`Workflow.compile()` validates it) |
| **State** | a step — every state declares `requires: list[Requirement]`; types differ by *who fills them* |
| **Requirement** | a field a state expects: `field`, `required` (default true), `type`, `options`, `condition` |
| **Transition** | a directed link, optionally guarded by a `Condition` (branching) |
| **Session** | one conversation's live run; drive it with `session.update(values)` |
| **Blackboard** | the shared, deterministic record of collected values |
| **Directive** | a fully-resolved instruction for your host to execute (never run by the machine) |
| **Blocker** | why the current step hasn't advanced: `MISSING` / `INVALID` / `AWAITING_*` |

## Documentation

- [Usage manual](https://github.com/geralm/markov-protocols/blob/main/docs/USAGE.md)
- [Design & architecture](https://github.com/geralm/markov-protocols/blob/main/docs/DESIGN.md)
- [Runnable example](https://github.com/geralm/markov-protocols/blob/main/example.py)

## Development

```bash
uv sync            # environment + dev tools
uv run pytest      # tests
uv run ruff check  # lint
uv run mypy        # type-check
```

## License

MIT
