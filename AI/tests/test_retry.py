import time

import pytest

from shared.retry import RetryTimeoutError, call_with_timeout_retry


def test_call_with_timeout_retry_returns_successful_result():
    attempts = 0

    def operation():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary failure")
        return "ok"

    result = call_with_timeout_retry(
        operation,
        timeout_seconds=1,
        max_retries=1,
        backoff_seconds=0,
        operation_name="test operation",
    )

    assert result == "ok"
    assert attempts == 2


def test_call_with_timeout_retry_times_out_and_retries():
    attempts = 0

    def operation():
        nonlocal attempts
        attempts += 1
        time.sleep(0.2)
        return "too late"

    try:
        call_with_timeout_retry(
            operation,
            timeout_seconds=0.01,
            max_retries=1,
            backoff_seconds=0,
            operation_name="test operation",
        )
    except RetryTimeoutError as e:
        assert "timed out" in str(e)
    else:
        pytest.fail("Expected RetryTimeoutError")

    assert attempts == 2
