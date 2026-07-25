"""Smoke tests for the Result pattern — confirms the scaffold is wired up."""

from markov_protocols import ErrorType, Result


def test_ok_carries_value() -> None:
    result: Result[int, str] = Result.ok(42)
    assert result.is_success
    assert result.is_failure is False
    assert result.value == 42
    assert result.error is ErrorType.NONE


def test_fail_carries_error() -> None:
    result: Result[int, str] = Result.fail(ErrorType.NOT_FOUND, "missing")
    assert result.is_failure
    assert result.error is ErrorType.NOT_FOUND
    assert result.error_details == "missing"
