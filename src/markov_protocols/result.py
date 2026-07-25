"""A lightweight Result/Error pattern used across the package.

Instead of raising exceptions, operations return a ``Result`` that is either a
success carrying a value, or a failure carrying an ``ErrorType`` and details.
This keeps control flow explicit and deterministic, which matters when the
output is meant to guide an AI agent.
"""

from __future__ import annotations

from enum import Enum


class ErrorType(Enum):
    """Coarse, transport-agnostic classification of a failure."""

    NONE = "NONE"  # No error occurred.
    NOT_FOUND = "NOT_FOUND"  # Something referenced doesn't exist.
    VALIDATION_ERROR = "VALIDATION"  # The input/definition is invalid.
    UNAUTHORIZED = "UNAUTHORIZED"  # Not allowed.
    CONFLICT = "CONFLICT"  # Ambiguous / conflicting state.
    INTERNAL_ERROR = "INTERNAL"  # Unexpected failure.


class Result[T, E]:
    """The outcome of an operation: either a success value or a typed error.

    Construct via the :meth:`ok` and :meth:`fail` factories rather than the
    initializer directly.
    """

    __slots__ = ("is_success", "value", "error", "error_details")

    def __init__(
        self,
        is_success: bool,
        value: T | None = None,
        error: ErrorType = ErrorType.NONE,
        error_details: E | None = None,
    ) -> None:
        self.is_success = is_success
        self.value = value
        self.error = error
        self.error_details = error_details

    @property
    def is_failure(self) -> bool:
        return not self.is_success

    @classmethod
    def ok(cls, value: T) -> Result[T, E]:
        """Build a successful result carrying ``value``."""
        return cls(is_success=True, value=value)

    @classmethod
    def fail(cls, error: ErrorType, error_details: E) -> Result[T, E]:
        """Build a failed result carrying an error type and details."""
        return cls(is_success=False, error=error, error_details=error_details)

    def unwrap(self) -> T:
        """Return the value, or raise ``ValueError`` if this is a failure.

        Use only at boundaries where a failure is genuinely unexpected; prefer
        checking ``is_success`` and reading ``value``/``error_details``.
        """
        if not self.is_success:
            raise ValueError(f"unwrap() on failed Result: {self.error.value}: {self.error_details}")
        return self.value  # type: ignore[return-value]

    def __bool__(self) -> bool:
        return self.is_success

    def __repr__(self) -> str:
        if self.is_success:
            return f"Result.ok({self.value!r})"
        return f"Result.fail({self.error.value}, {self.error_details!r})"
