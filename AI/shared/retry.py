from __future__ import annotations

import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import TypeVar


T = TypeVar("T")


logger = logging.getLogger(__name__)


class RetryTimeoutError(TimeoutError):
    pass


def call_with_timeout_retry(
    operation: Callable[[], T],
    *,
    timeout_seconds: float,
    max_retries: int,
    backoff_seconds: float,
    operation_name: str,
) -> T:
    attempts = max_retries + 1
    last_error: BaseException | None = None

    for attempt in range(1, attempts + 1):
        try:
            return _call_with_timeout(operation, timeout_seconds)
        except FutureTimeoutError as e:
            last_error = RetryTimeoutError(
                f"{operation_name} timed out after {timeout_seconds}s"
            )
            logger.warning(
                "%s timed out after %ss (attempt %s/%s)",
                operation_name,
                timeout_seconds,
                attempt,
                attempts,
            )
        except Exception as e:
            last_error = e
            logger.warning(
                "%s failed (attempt %s/%s): %s",
                operation_name,
                attempt,
                attempts,
                e,
            )

        if attempt < attempts:
            time.sleep(backoff_seconds * attempt)

    if last_error is not None:
        raise last_error

    raise RuntimeError(f"{operation_name} failed without an error")


def _call_with_timeout(operation: Callable[[], T], timeout_seconds: float) -> T:
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(operation)
    try:
        result = future.result(timeout=timeout_seconds)
    except FutureTimeoutError:
        future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
        raise
    except Exception:
        executor.shutdown(wait=False, cancel_futures=True)
        raise
    else:
        executor.shutdown(wait=False)
        return result
