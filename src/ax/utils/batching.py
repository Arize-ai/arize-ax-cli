"""Batched uploads with retry and backoff for large example payloads.

Dataset writes send every example in a single HTTP request. Large payloads
(hundreds of examples with long string fields) make the server reject the
request with HTTP 500, and bursts of sequential writes draw HTTP 429. The
SDK's own transport picker does not save us here: it sizes a
``list[dict]`` payload with :func:`sys.getsizeof`, which measures the dict
containers but not the strings they point at, so a multi-megabyte payload
can be estimated at a fraction of its real size and still be routed over
REST as one request.

This module splits a payload into batches that are bounded by *both* row
count and real serialized size, then sends each batch through a retry loop
that backs off on transient failures only. It is deliberately free of
console output so it stays easy to unit test; callers pass ``on_progress``
and ``on_retry`` callbacks to drive their own UI.
"""

from __future__ import annotations

import json
import logging
import random
import time
from typing import TYPE_CHECKING, TypeVar

from ax.core.error_formatter import parse_exception
from ax.core.exceptions import BatchUploadError

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

logger = logging.getLogger(__name__)

T = TypeVar("T")

#: Examples per API call when batching is enabled.
DEFAULT_BATCH_SIZE = 50

#: Retry attempts per batch, on top of the initial attempt.
DEFAULT_MAX_RETRIES = 3

#: Serialized-size ceiling per batch. Kept well under typical server body
#: limits so that a batch of wide rows (long strings, URLs) still fits.
MAX_BATCH_BYTES = 4 * 1024 * 1024

#: Backoff bounds, in seconds.
INITIAL_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 60.0

#: Statuses worth retrying: rate limits, request timeouts, and the
#: transient server-side failures. Client errors such as 400 (bad payload),
#: 401/403 (auth) and 409 (conflict) fail fast — retrying cannot fix them.
RETRYABLE_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})


def _row_bytes(row: dict[str, object]) -> int:
    """Return the approximate serialized size of a single example, in bytes."""
    try:
        return len(json.dumps(row, default=str).encode("utf-8"))
    except (TypeError, ValueError):
        # Unserializable rows are the server's problem to report; for
        # sizing purposes a rough estimate is enough.
        return len(str(row).encode("utf-8"))


def chunk_examples(
    examples: Sequence[dict[str, object]],
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_bytes: int = MAX_BATCH_BYTES,
) -> list[list[dict[str, object]]]:
    """Split examples into batches bounded by row count and serialized size.

    A batch is closed when it reaches ``batch_size`` rows or when adding the
    next row would push it past ``max_bytes``. A single row larger than
    ``max_bytes`` is still emitted on its own rather than dropped, so every
    input row appears in exactly one batch.

    Args:
        examples: Examples to split. Order is preserved.
        batch_size: Maximum rows per batch. ``0`` disables splitting and
            returns the whole payload as one batch.
        max_bytes: Maximum approximate serialized bytes per batch.

    Returns:
        A list of batches. Empty input yields an empty list.
    """
    if not examples:
        return []
    if batch_size <= 0:
        return [list(examples)]

    batches: list[list[dict[str, object]]] = []
    current: list[dict[str, object]] = []
    current_bytes = 0

    for row in examples:
        row_bytes = _row_bytes(row)
        exceeds_bytes = current and current_bytes + row_bytes > max_bytes
        if len(current) == batch_size or exceeds_bytes:
            batches.append(current)
            current = []
            current_bytes = 0
        current.append(row)
        current_bytes += row_bytes

    if current:
        batches.append(current)
    return batches


def http_status(exc: BaseException) -> int | None:
    """Return the HTTP status behind an exception, or ``None`` if unknown.

    Delegates to :func:`ax.core.error_formatter.parse_exception`, which walks
    the ``__cause__`` chain and understands the SDK's ``ApiException`` as well
    as gRPC/Flight errors, so status detection does not rely on matching
    substrings in error text.
    """
    if not isinstance(exc, Exception):
        return None
    parsed = parse_exception(exc)
    return parsed.status if parsed else None


def retry_after_seconds(exc: BaseException) -> float | None:
    """Return the server's ``Retry-After`` delay in seconds, if it sent one.

    Only the delta-seconds form is honored; an HTTP-date value falls back to
    the computed backoff. The value is clamped to :data:`MAX_BACKOFF_SECONDS`
    so a hostile or mistaken header cannot stall the CLI indefinitely.
    """
    if not isinstance(exc, Exception):
        return None
    parsed = parse_exception(exc)
    if not parsed or not parsed.headers:
        return None

    for key, value in parsed.headers.items():
        if str(key).lower() != "retry-after":
            continue
        try:
            seconds = float(str(value).strip())
        except ValueError:
            return None
        return min(max(seconds, 0.0), MAX_BACKOFF_SECONDS)
    return None


def is_retryable(exc: BaseException) -> bool:
    """Report whether retrying the same request could plausibly succeed.

    A known status decides the answer outright. Without one, only transport
    level failures (a dropped connection, a timeout) are retried; anything
    else is treated as a permanent error so a malformed payload fails
    immediately instead of being sent four times.
    """
    status = http_status(exc)
    if status is not None:
        return status in RETRYABLE_STATUSES
    return isinstance(exc, (TimeoutError, ConnectionError))


def backoff_delay(
    attempt: int,
    *,
    retry_after: float | None = None,
    rng: random.Random | None = None,
) -> float:
    """Return the delay before retry number ``attempt`` (0-based).

    Uses equal-jitter exponential backoff: the delay is drawn from the top
    half of an exponentially growing window, which spreads retries from
    concurrent CLI runs without letting any single delay collapse to zero.
    An explicit ``Retry-After`` from the server wins over the computed value.
    """
    if retry_after is not None:
        return retry_after
    ceiling = min(
        INITIAL_BACKOFF_SECONDS * (2**attempt),
        MAX_BACKOFF_SECONDS,
    )
    # Not security-sensitive: jitter only needs to de-correlate retries.
    jitter = (rng or random).random()
    return ceiling * (0.5 + 0.5 * jitter)


def send_batches(
    batches: Sequence[Sequence[dict[str, object]]],
    send: Callable[[list[dict[str, object]]], T],
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
    on_progress: Callable[[int], None] | None = None,
    on_retry: Callable[[int, int, float, Exception], None] | None = None,
    sleep: Callable[[float], None] | None = None,
    rng: random.Random | None = None,
) -> list[T]:
    """Send each batch through ``send``, retrying transient failures.

    Batches are sent in order and the run stops at the first batch that
    cannot be delivered, so the caller can report exactly how much of the
    payload landed instead of leaving the user to guess.

    Args:
        batches: Batches to send, as produced by :func:`chunk_examples`.
        send: Callable that uploads one batch and returns the API response.
        max_retries: Retry attempts per batch, on top of the initial attempt.
        on_progress: Called with the row count of each delivered batch.
        on_retry: Called as ``(batch_number, attempt, delay, exc)`` before
            each sleep, where both numbers are 1-based.
        sleep: Sleep function; injectable for tests.
        rng: Random source for jitter; injectable for tests.

    Returns:
        The response from each batch, in order.

    Raises:
        BatchUploadError: If a batch still fails once retries are exhausted,
            or fails with a non-retryable error. The exception records how
            many examples were uploaded before the failure.
    """
    sleep_fn = sleep if sleep is not None else time.sleep
    total_rows = sum(len(batch) for batch in batches)
    responses: list[T] = []
    uploaded = 0

    for index, batch in enumerate(batches):
        rows = list(batch)
        attempt = 0
        while True:
            try:
                response = send(rows)
            # PERF203: the try/except is the retry loop itself, and the
            # cost of a handler is noise next to a network round trip.
            except Exception as exc:  # noqa: PERF203
                is_last = attempt >= max_retries
                if is_last or not is_retryable(exc):
                    raise _batch_failure(
                        exc,
                        batch_number=index + 1,
                        batch_count=len(batches),
                        first_row=uploaded + 1,
                        last_row=uploaded + len(rows),
                        attempts=attempt + 1,
                        uploaded=uploaded,
                        total=total_rows,
                    ) from exc
                delay = backoff_delay(
                    attempt,
                    retry_after=retry_after_seconds(exc),
                    rng=rng,
                )
                logger.debug(
                    "Batch %d/%d failed (%s); retrying in %.1fs "
                    "(attempt %d of %d)",
                    index + 1,
                    len(batches),
                    exc,
                    delay,
                    attempt + 1,
                    max_retries,
                )
                if on_retry is not None:
                    on_retry(index + 1, attempt + 1, delay, exc)
                sleep_fn(delay)
                attempt += 1
            else:
                responses.append(response)
                uploaded += len(rows)
                if on_progress is not None:
                    on_progress(len(rows))
                break

    return responses


def _batch_failure(
    exc: Exception,
    *,
    batch_number: int,
    batch_count: int,
    first_row: int,
    last_row: int,
    attempts: int,
    uploaded: int,
    total: int,
) -> BatchUploadError:
    """Build the error describing which batch failed and what got through."""
    status = http_status(exc)
    status_note = f" (HTTP {status})" if status is not None else ""
    attempt_note = (
        f" after {attempts} attempts" if attempts > 1 else " on first attempt"
    )
    message = (
        f"batch {batch_number} of {batch_count} "
        f"(examples {first_row}-{last_row}) failed{status_note}"
        f"{attempt_note}: {exc}"
    )
    if batch_count > 1:
        message += (
            f". {uploaded} of {total} example(s) were uploaded "
            "before the failure"
        )
    return BatchUploadError(message, uploaded=uploaded, total=total)
