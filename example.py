"""A runnable tour of markov-protocols.

Run it with:  uv run python example.py

It walks a small real-estate intake workflow through three scenarios:
  1. the happy path (with a host-run action),
  2. a mid-conversation correction that reopens an already-sent action,
  3. branching on an extracted intent.

The machine here is deterministic; the "agent" and "host" parts are faked with
plain print statements to keep the example dependency-free.
"""

from __future__ import annotations

from markov_protocols import (
    ActionExecuteState,
    DataCollectionState,
    Eq,
    Ref,
    Requirement,
    Session,
    Transition,
    UpdateResult,
    Workflow,
)


def build_intake_workflow() -> Workflow:
    """collect-email -> send-confirmation (action) -> collect-budget."""
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
    return result.value


def show(outcome: UpdateResult) -> None:
    """Print the deterministic snapshot an agent would read after each update."""
    print(f"    now at .......... {outcome.current_state.id}")
    print(f"    events .......... {[type(e).__name__ for e in outcome.events]}")
    if outcome.missing_fields:
        print(f"    still needs ..... {outcome.missing_fields}")
    if outcome.directive and outcome.directive.ready:
        print(f"    host must run ... {outcome.directive.payload}")
    if outcome.is_finished:
        print("    workflow finished ✅")


def demo_happy_path_and_correction() -> None:
    print("\n=== 1 & 2. Happy path, then a correction ===")
    session = Session.start(build_intake_workflow())

    print("\n> customer gives their email")
    show(session.update({"email": "pedro@example.com"}).value)

    print("\n> host sends the confirmation and reports the result")
    session.update({"confirmation_sent": True})

    print("\n> customer gives their budget — workflow completes")
    show(session.update({"budget": 5000}).value)

    print("\n> customer corrects their email AFTER the confirmation went out")
    outcome = session.update({"email": "nonpedro@example.com"}).value
    show(outcome)
    for event in outcome.events:
        if type(event).__name__ == "StateReopened" and event.had_executed:  # type: ignore[attr-defined]
            print(f"    ⚠ '{event.state_id}' already ran — host should resend")  # type: ignore[attr-defined]

    print("\n> host resends to the corrected address; the tail settles for free")
    show(session.update({"confirmation_sent": True}).value)


def demo_branching() -> None:
    print("\n=== 3. Branching on intent ===")
    workflow = Workflow.compile(
        name="triage",
        initial="Detect intent",
        states=[
            DataCollectionState(title="Detect intent", requires=[Requirement(field="intent")]),
            DataCollectionState(title="Sales flow", requires=[Requirement(field="budget")]),
            DataCollectionState(title="Support flow", requires=[Requirement(field="issue")]),
        ],
        transitions=[
            Transition(
                source_id="detect-intent",
                target_id="sales-flow",
                guard=Eq(field="intent", value="buy"),
            ),
            Transition(
                source_id="detect-intent",
                target_id="support-flow",
                guard=Eq(field="intent", value="support"),
            ),
        ],
    ).value

    for intent in ("buy", "support"):
        session = Session.start(workflow)
        outcome = session.update({"intent": intent}).value
        print(f"\n> intent = {intent!r} routed to '{outcome.current_state.id}'")


if __name__ == "__main__":
    demo_happy_path_and_correction()
    demo_branching()
