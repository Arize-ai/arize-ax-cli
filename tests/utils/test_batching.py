"""Tests for batched uploads with retry and backoff."""

import random

import pytest
from arize import ApiException

from ax.core.exceptions import APIError, BatchUploadError
from ax.utils.batching import (
    INITIAL_BACKOFF_SECONDS,
    MAX_BACKOFF_SECONDS,
    backoff_delay,
    chunk_examples,
    http_status,
    is_retryable,
    retry_after_seconds,
    send_batches,
)


def api_error(status: int, headers: dict | None = None) -> ApiException:
    """Build an SDK ApiException carrying a status and optional headers."""
    exc = ApiException(status=status, reason="test")
    exc.headers = headers
    return exc


def rows(count: int, *, width: int = 1) -> list[dict[str, object]]:
    """Build `count` distinct example rows."""
    return [{f"f{i}": f"row-{n}" for i in range(width)} for n in range(count)]


class TestChunkExamples:
    """Tests for splitting a payload into batches."""

    def test_splits_on_row_count(self):
        batches = chunk_examples(rows(120), batch_size=50)
        assert [len(b) for b in batches] == [50, 50, 20]

    def test_preserves_every_row_in_order(self):
        examples = rows(57)
        flattened = [
            row
            for batch in chunk_examples(examples, batch_size=10)
            for row in batch
        ]
        assert flattened == examples

    def test_exact_multiple_does_not_emit_empty_batch(self):
        batches = chunk_examples(rows(100), batch_size=50)
        assert [len(b) for b in batches] == [50, 50]

    def test_payload_under_batch_size_is_one_batch(self):
        batches = chunk_examples(rows(10), batch_size=50)
        assert batches == [rows(10)]

    def test_empty_payload_yields_no_batches(self):
        assert chunk_examples([], batch_size=50) == []

    def test_batch_size_zero_disables_splitting(self):
        examples = rows(500)
        assert chunk_examples(examples, batch_size=0) == [examples]

    def test_splits_on_serialized_size_before_row_count(self):
        """Wide rows split early, which is the case the row count alone misses."""
        examples = [
            {"url": "https://example.com/" + "x" * 900} for _ in range(10)
        ]
        batches = chunk_examples(examples, batch_size=50, max_bytes=3000)
        assert len(batches) > 1
        assert sum(len(b) for b in batches) == 10

    def test_single_oversized_row_is_still_emitted(self):
        examples = [{"blob": "x" * 5000}, {"blob": "small"}]
        batches = chunk_examples(examples, batch_size=50, max_bytes=100)
        assert [len(b) for b in batches] == [1, 1]

    def test_unserializable_row_is_sized_not_dropped(self):
        examples: list[dict[str, object]] = [{"when": object()}, {"a": 1}]
        batches = chunk_examples(examples, batch_size=10)
        assert batches == [examples]


class TestErrorClassification:
    """Tests for deciding whether a failure is worth retrying."""

    @pytest.mark.parametrize("status", [408, 425, 429, 500, 502, 503, 504])
    def test_transient_statuses_are_retryable(self, status):
        assert is_retryable(api_error(status)) is True

    @pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 422, 501])
    def test_client_errors_are_not_retryable(self, status):
        assert is_retryable(api_error(status)) is False

    def test_transport_failures_are_retryable(self):
        assert is_retryable(TimeoutError("timed out")) is True
        assert is_retryable(ConnectionError("reset by peer")) is True

    def test_unknown_errors_are_not_retryable(self):
        assert is_retryable(ValueError("bad payload")) is False

    def test_status_is_read_from_the_exception_not_its_text(self):
        """A 400 that merely mentions 429 in its body must not be retried."""
        exc = api_error(400)
        exc.body = "rejected: upstream reported 429 Too Many Requests"
        assert http_status(exc) == 400
        assert is_retryable(exc) is False

    def test_status_is_found_through_the_cause_chain(self):
        wrapper = APIError("Failed to append examples: rate limited")
        wrapper.__cause__ = api_error(429)
        assert http_status(wrapper) == 429

    def test_missing_status_reads_as_unknown(self):
        assert http_status(ValueError("boom")) is None


class TestRetryAfter:
    """Tests for honoring the server's Retry-After header."""

    def test_delta_seconds_are_honored(self):
        assert retry_after_seconds(api_error(429, {"Retry-After": "7"})) == 7.0

    def test_header_lookup_is_case_insensitive(self):
        assert retry_after_seconds(api_error(429, {"retry-after": "3"})) == 3.0

    def test_value_is_clamped_to_the_backoff_ceiling(self):
        headers = {"Retry-After": str(MAX_BACKOFF_SECONDS * 100)}
        assert (
            retry_after_seconds(api_error(429, headers)) == MAX_BACKOFF_SECONDS
        )

    def test_negative_value_is_floored_at_zero(self):
        assert retry_after_seconds(api_error(429, {"Retry-After": "-5"})) == 0.0

    def test_http_date_form_falls_back_to_computed_backoff(self):
        headers = {"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}
        assert retry_after_seconds(api_error(429, headers)) is None

    def test_absent_header_reads_as_none(self):
        assert retry_after_seconds(api_error(429)) is None


class TestBackoffDelay:
    """Tests for the backoff schedule."""

    def test_delay_grows_with_each_attempt(self):
        rng = random.Random(0)
        delays = [backoff_delay(n, rng=rng) for n in range(4)]
        assert delays == sorted(delays)
        assert delays[0] < delays[-1]

    def test_delay_stays_within_its_jitter_window(self):
        rng = random.Random(1)
        for attempt in range(6):
            ceiling = min(
                INITIAL_BACKOFF_SECONDS * 2**attempt, MAX_BACKOFF_SECONDS
            )
            delay = backoff_delay(attempt, rng=rng)
            assert ceiling / 2 <= delay <= ceiling

    def test_delay_never_exceeds_the_ceiling(self):
        rng = random.Random(2)
        assert backoff_delay(50, rng=rng) <= MAX_BACKOFF_SECONDS

    def test_jitter_spreads_retries_apart(self):
        rng = random.Random(3)
        assert len({backoff_delay(3, rng=rng) for _ in range(20)}) > 1

    def test_retry_after_overrides_the_computed_delay(self):
        assert backoff_delay(0, retry_after=12.5) == 12.5


class TestSendBatches:
    """Tests for delivering batches with retries."""

    def test_sends_every_batch_in_order(self):
        seen = []
        batches = chunk_examples(rows(25), batch_size=10)
        responses = send_batches(
            batches, lambda b: seen.append(b) or f"ok-{len(b)}"
        )
        assert [len(b) for b in seen] == [10, 10, 5]
        assert responses == ["ok-10", "ok-10", "ok-5"]

    def test_reports_progress_per_delivered_batch(self):
        advanced = []
        batches = chunk_examples(rows(25), batch_size=10)
        send_batches(batches, lambda b: None, on_progress=advanced.append)
        assert advanced == [10, 10, 5]
        assert sum(advanced) == 25

    def test_retries_a_rate_limited_batch_then_succeeds(self):
        calls = {"n": 0}
        slept = []

        def send(batch):
            calls["n"] += 1
            if calls["n"] < 3:
                raise api_error(429)
            return "ok"

        responses = send_batches(
            [rows(5)],
            send,
            max_retries=3,
            sleep=slept.append,
            rng=random.Random(0),
        )
        assert responses == ["ok"]
        assert calls["n"] == 3
        assert len(slept) == 2
        assert slept == sorted(slept), (
            "backoff should not shrink between retries"
        )

    def test_waits_for_the_server_requested_delay(self):
        calls = {"n": 0}
        slept = []

        def send(batch):
            calls["n"] += 1
            if calls["n"] == 1:
                raise api_error(429, {"Retry-After": "9"})
            return "ok"

        send_batches([rows(2)], send, sleep=slept.append)
        assert slept == [9.0]

    def test_retries_transient_server_errors(self):
        calls = {"n": 0}

        def send(batch):
            calls["n"] += 1
            if calls["n"] == 1:
                raise api_error(503)
            return "ok"

        assert send_batches([rows(2)], send, sleep=lambda _: None) == ["ok"]
        assert calls["n"] == 2

    def test_client_errors_fail_without_retrying(self):
        calls = {"n": 0}

        def send(batch):
            calls["n"] += 1
            raise api_error(400)

        with pytest.raises(BatchUploadError) as exc_info:
            send_batches([rows(5)], send, max_retries=5, sleep=lambda _: None)
        assert calls["n"] == 1, "a rejected payload must not be resent"
        assert "HTTP 400" in str(exc_info.value)

    def test_gives_up_after_max_retries(self):
        calls = {"n": 0}

        def send(batch):
            calls["n"] += 1
            raise api_error(429)

        with pytest.raises(BatchUploadError):
            send_batches(
                [rows(5)],
                send,
                max_retries=2,
                sleep=lambda _: None,
                rng=random.Random(0),
            )
        assert calls["n"] == 3, "one initial attempt plus max_retries"

    def test_max_retries_zero_means_a_single_attempt(self):
        calls = {"n": 0}

        def send(batch):
            calls["n"] += 1
            raise api_error(500)

        with pytest.raises(BatchUploadError):
            send_batches([rows(1)], send, max_retries=0, sleep=lambda _: None)
        assert calls["n"] == 1

    def test_failure_reports_how_much_landed(self):
        def send(batch):
            if len(batch) == 10 and batch[0]["f0"] == "row-20":
                raise api_error(500)
            return "ok"

        batches = chunk_examples(rows(35), batch_size=10)
        with pytest.raises(BatchUploadError) as exc_info:
            send_batches(batches, send, max_retries=0, sleep=lambda _: None)

        err = exc_info.value
        assert err.uploaded == 20
        assert err.total == 35
        assert "batch 3 of 4" in str(err)
        assert "examples 21-30" in str(err)
        assert "20 of 35" in str(err)

    def test_failure_stops_before_later_batches(self):
        seen = []

        def send(batch):
            seen.append(batch)
            raise api_error(500)

        with pytest.raises(BatchUploadError):
            send_batches(
                chunk_examples(rows(30), batch_size=10),
                send,
                max_retries=0,
                sleep=lambda _: None,
            )
        assert len(seen) == 1, "no point sending the rest once one batch fails"

    def test_failure_keeps_the_original_error_as_the_cause(self):
        original = api_error(500)

        def send(batch):
            raise original

        with pytest.raises(BatchUploadError) as exc_info:
            send_batches([rows(1)], send, max_retries=0, sleep=lambda _: None)
        assert exc_info.value.__cause__ is original

    def test_retry_callback_describes_each_retry(self):
        calls = {"n": 0}
        notices = []

        def send(batch):
            calls["n"] += 1
            if calls["n"] < 3:
                raise api_error(429)
            return "ok"

        send_batches(
            [rows(1)],
            send,
            on_retry=lambda *a: notices.append(a),
            sleep=lambda _: None,
        )
        assert [n[0] for n in notices] == [1, 1], "both retries are on batch 1"
        assert [n[1] for n in notices] == [1, 2], "attempt numbers are 1-based"
        assert all(isinstance(n[2], float) for n in notices)

    def test_no_batches_is_a_no_op(self):
        assert send_batches([], lambda b: "ok") == []
