# Usage manual

`markov-protocols` is a deterministic finite state machine for modeling workflows that guide an AI
agent. You **author** a workflow, **run** a session, and feed the session the data your agent
extracts from the conversation. The machine deterministically decides where the workflow goes next
and what the host must do — it never calls an LLM, runs a tool, or performs any I/O itself.

- Architecture and rationale: [`DESIGN.md`](DESIGN.md)
- A runnable end-to-end script: [`../example.py`](../example.py) — `uv run python example.py`

---

## 1. Install

```bash
uv add markov-protocols
# or
pip install markov-protocols
```

Requires Python ≥ 3.13. The package ships type information (`py.typed`).

---

## 2. The mental model in one paragraph

A **Workflow** is a graph of **States** connected by **Transitions**. A running workflow is a
**Session**; everything the agent collects lives in one shared **Blackboard**. Each state declares a
**completion condition** over the Blackboard; when it holds, the session advances along the first
enabled **Transition** (its **guard**, a boolean `Condition`, must hold). A **Ref** binds a collected
value into a payload (e.g. a webhook body). You drive everything with a single verb —
`session.update(values)` — and read back a deterministic snapshot.

---

## 3. Author a workflow

State ids are derived automatically as the slug of the title (`"Collect email" → "collect-email"`);
transitions reference those ids. `Workflow.compile(...)` validates the graph and returns a `Result`.

```python
from markov_protocols import (
    Workflow, DataCollectionState, ActionExecuteState, Requirement, Transition, Ref, Eq,
)

result = Workflow.compile(
    name="real-estate-intake",
    initial="Collect email",
    states=[
        DataCollectionState(title="Collect email", requires=[Requirement(field="email")]),
        ActionExecuteState(
            title="Send confirmation",
            payload={"to": Ref(field="email"), "template": "welcome"},
            result_field="confirmation_sent",
        ),
        DataCollectionState(title="Collect budget", requires=[Requirement(field="budget")]),
    ],
    transitions=[
        Transition(source_id="collect-email", target_id="send-confirmation"),
        Transition(source_id="send-confirmation", target_id="collect-budget"),
    ],
)

if result.is_failure:
    raise SystemExit(f"invalid workflow: {result.error_details}")
workflow = result.value
```

### State types

| State | Completes when | Use for |
|---|---|---|
| `DataCollectionState(requires=[...])` | every required field exists (and any per-field `condition` holds) | gathering data from the user |
| `ActionExecuteState(result_field=..., payload={...})` | the host writes `result_field` | a side effect the host runs (webhook, tool, …) |
| `HumanHandoffState(resolution_field=..., notify={...})` | the host writes `resolution_field` | escalating to a human |

---

## 4. Run a session

```python
from markov_protocols import Session

session = Session.start(workflow)
session.id             # a unique run id (uuid4)
session.current_state  # where the workflow is now

outcome = session.update({"email": "pedro@example.com"}).value
```

`update()` applies the values, then **fast-forwards**: it keeps completing the current state and
stepping to the next one for as long as the data allows. So one call can advance through several
states (handy when the user answers everything at once), or hold position when they don't.

`update()` returns a `Result[UpdateResult, str]`. The `UpdateResult` is your snapshot:

| Field | Meaning |
|---|---|
| `current_state` | the state the workflow now sits on — read `current_state.metadata.prompts` to guide your agent |
| `missing_fields` | data the current state is still waiting for |
| `available_transitions` | transitions that could fire next |
| `directive` | the host action to run now (see below), or `None` |
| `events` | what happened during this call |
| `is_finished` | the workflow reached a terminal state |

### Directives (host actions)

When the current state is an action/handoff, the machine hands you a **Directive**: a fully-resolved
instruction to execute. It never runs it for you.

```python
outcome = session.update({}).value
if outcome.directive and outcome.directive.ready:
    send_webhook(outcome.directive.payload)      # {"to": "pedro@example.com", "template": "welcome"}
    session.update({"confirmation_sent": True})  # report the result back
```

`directive.ready` is `False` (with `directive.missing` naming the fields) until every `Ref` resolves,
so you can never fire a side effect with a blank value.

---

## 5. Corrections handle themselves

Feed corrections the same way — there is no special API. If a field a completed state depends on
changes, the machine reopens that state, rewinds to the earliest affected step, clears any already-run
action so it re-runs, and tells you via events.

```python
outcome = session.update({"email": "new@example.com"}).value
for event in outcome.events:
    print(type(event).__name__, event)
# ValueChanged(...), StateReopened(state_id="collect-email", had_executed=False),
# StateReopened(state_id="send-confirmation", had_executed=True),  <-- resend!
# ...
```

A `StateReopened` with `had_executed=True` means that step already performed a side effect — your
host should compensate (e.g. resend to the corrected address). The reopened action's directive
re-materializes with the new value automatically.

---

## 6. The host loop

Putting it together, your integration loop looks like:

```python
session = Session.start(workflow)
while not session.is_finished:
    values = your_llm.extract(conversation, session.current_state)  # your job (stochastic)
    outcome = session.update(values).value                          # the machine (deterministic)

    if outcome.directive and outcome.directive.ready:
        result_field, result = your_host.run(outcome.directive.payload)
        session.update({result_field: result})

    your_agent.guide(outcome.current_state, outcome.missing_fields)  # your job
```

The machine is the deterministic referee; your host owns everything stochastic or with side effects.

---

## 7. Persistence

A session is fully described by its id, blackboard values, current state, statuses, and history —
all serializable. Persist those and rehydrate with `Session.resume(...)`:

```python
saved = {
    "id": session.id,
    "values": session.blackboard.to_dict(),
    "current_id": session.current_state.id,
    "statuses": session.statuses,
    "history": session.history,
}
resumed = Session.resume(workflow, **saved)
```

---

## 8. Conditions & guards

Conditions are a small, typed, JSON-serializable vocabulary evaluated over the Blackboard. Use them
for per-field requirements and for transition guards (branching).

```python
from markov_protocols import All, Any, Not, Eq, Exists, In, Regex, Gt

# Branch on an extracted discriminator:
Transition(source_id="triage", target_id="sales",   guard=Eq(field="intent", value="buy"))
Transition(source_id="triage", target_id="support", guard=Eq(field="intent", value="support"))

# A stricter requirement:
Requirement(field="email", condition=Regex(field="email", value=r"^[^@]+@[^@]+$"))

# Combine:
All(of=[Exists(field="email"), Gt(field="budget", value=1000)])
```

Available: `Exists`, `Eq`, `Ne`, `In`, `Regex`, `Gt`, `Gte`, `Lt`, `Lte`, and the combinators
`All`, `Any`, `Not`. A condition over a missing field is always `False` and never raises.

---

## 9. Extending with your own state type

You are not limited to the three built-ins. Subclass `State`, implement the interface, and register
the type so it round-trips through JSON — with no changes to the engine.

```python
from typing import Literal
from markov_protocols import State, Condition, Exists, state_registry

class ApprovalState(State):
    type: Literal["APPROVAL"] = "APPROVAL"
    approved_field: str

    def completion_condition(self) -> Condition:
        return Exists(field=self.approved_field)

    def depends_on(self) -> set[str]:
        return {self.approved_field}

state_registry.register(ApprovalState)
```

See [`DESIGN.md`](DESIGN.md) §5 and §12 for the full extension playbook.
