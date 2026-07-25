"""markov-protocols: a deterministic finite state machine for modeling
workflows that guide AI agents.

Author with ``Workflow`` + the concrete state types, express logic with
``Condition`` + ``Ref``, and handle outcomes with ``Result``. The runtime
(``Session``) arrives in a later slice.
"""

from .conditions import (
    All,
    Any,
    Condition,
    Eq,
    Exists,
    Gt,
    Gte,
    In,
    Lt,
    Lte,
    Ne,
    Not,
    Regex,
    condition_fields,
    evaluate,
)
from .definition.metadata import StateMetadata, TransitionMetadata
from .definition.registry import state_registry
from .definition.state import Directive, Requirement, State, Status
from .definition.states import ActionExecuteState, DataCollectionState, HumanHandoffState
from .definition.transition import Transition
from .definition.workflow import Workflow
from .references import Ref, referenced_fields, resolve
from .result import ErrorType, Result
from .runtime.blackboard import Blackboard
from .runtime.events import (
    ActionExecuted,
    Event,
    StateCompleted,
    StateReopened,
    TransitionTaken,
    ValueChanged,
    ValueSet,
)
from .runtime.session import Session, UpdateResult
from .slug import slugify

__all__ = [
    "ActionExecuteState",
    "ActionExecuted",
    "All",
    "Any",
    "Blackboard",
    "Condition",
    "DataCollectionState",
    "Directive",
    "Eq",
    "ErrorType",
    "Event",
    "Exists",
    "Gt",
    "Gte",
    "HumanHandoffState",
    "In",
    "Lt",
    "Lte",
    "Ne",
    "Not",
    "Ref",
    "Regex",
    "Requirement",
    "Result",
    "Session",
    "State",
    "StateCompleted",
    "StateMetadata",
    "StateReopened",
    "Status",
    "Transition",
    "TransitionMetadata",
    "TransitionTaken",
    "UpdateResult",
    "ValueChanged",
    "ValueSet",
    "Workflow",
    "condition_fields",
    "evaluate",
    "referenced_fields",
    "resolve",
    "slugify",
    "state_registry",
]
