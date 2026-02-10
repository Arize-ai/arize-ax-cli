"""Error parsing and formatting utilities for CLI error messages.

This module provides utilities to parse ApiException objects from the Arize SDK
and format them into user-friendly error messages. It extracts structured error
information from RFC 9457 Problem Details and provides helpful suggestions.
"""

import re
import sys
from dataclasses import dataclass

from arize._generated.api_client.exceptions import ApiException
from arize._generated.api_client.models.problem import Problem

# Map gRPC codes to HTTP status
grpc_to_http = {
    0: (200, "OK"),  # OK
    1: (499, "Client Closed Request"),  # CANCELLED (used by proxies)
    2: (500, "Internal Server Error"),  # UNKNOWN
    3: (400, "Invalid Argument"),  # INVALID_ARGUMENT
    4: (504, "Gateway Timeout"),  # DEADLINE_EXCEEDED
    5: (404, "Not Found"),  # NOT_FOUND
    6: (409, "Conflict"),  # ALREADY_EXISTS
    7: (403, "Permission Denied"),  # PERMISSION_DENIED
    8: (429, "Too Many Requests"),  # RESOURCE_EXHAUSTED
    9: (412, "Failed Precondition"),  # FAILED_PRECONDITION
    10: (409, "Conflict"),  # ABORTED
    11: (400, "Out of Range"),  # OUT_OF_RANGE
    12: (501, "Not Implemented"),  # UNIMPLEMENTED
    13: (500, "Internal Server Error"),  # INTERNAL
    14: (503, "Service Unavailable"),  # UNAVAILABLE
    15: (500, "Internal Server Error"),  # DATA_LOSS
    16: (401, "Unauthenticated"),  # UNAUTHENTICATED
}


@dataclass
class ParsedError:
    """Structured error information extracted from an ApiException."""

    title: str | None = None
    status: int | None = None
    type: str | None = None
    detail: str | None = None
    instance: str | None = None
    reason: str | None = None
    headers: dict | None = None
    body: str | None = None


def parse_api_exception(exception: Exception) -> ParsedError | None:
    """Parse an exception chain to extract structured API error information.

    Walks the exception chain using __cause__ to find the original ApiException.
    Extracts status, reason, and Problem model data if available.

    Args:
        exception: The exception to parse (typically an AxError)

    Returns:
        ParsedError with extracted information, or None if no ApiException found
    """
    # Walk the exception chain to find ApiException
    current: BaseException | None = exception
    api_exception = None

    while current is not None:
        if isinstance(current, ApiException):
            api_exception = current
            break
        current = getattr(current, "__cause__", None)

    if api_exception is None:
        return None

    # Extract basic information
    parsed = ParsedError(
        status=api_exception.status,
        reason=api_exception.reason,
        headers=dict(api_exception.headers) if api_exception.headers else None,
        body=api_exception.body,
    )

    # Extract Problem model data if available
    if hasattr(api_exception, "data") and isinstance(
        api_exception.data, Problem
    ):
        problem = api_exception.data
        parsed.title = problem.title
        parsed.detail = problem.detail
        parsed.type = problem.type
        parsed.instance = problem.instance

    return parsed


def parse_grpc_error(exception: Exception) -> ParsedError | None:
    """Parse gRPC/Flight error messages from RuntimeError.

    Extracts useful information from flight client RuntimeError messages that contain
    gRPC debug context. Example error:
    "Flight returned invalid argument error, with message: dataset X already exists.
     gRPC client debug context: ..."

    Args:
        exception: The exception to parse (typically wraps a RuntimeError)

    Returns:
        ParsedError with extracted information, or None if no gRPC error found
    """
    # Walk exception chain looking for RuntimeError
    current: BaseException | None = exception
    while current is not None:
        if isinstance(current, RuntimeError):
            error_text = str(current)

            # Extract message using regex
            # Pattern: 'with message: "actual message"' or 'grpc_message:"message"'
            message_match = re.search(
                r"with message:\s*([^.]+)\.?\s*gRPC", error_text
            )
            if not message_match:
                message_match = re.search(r'grpc_message:"([^"]+)"', error_text)

            if message_match:
                user_message = message_match.group(1).strip()

                # Map gRPC status code to HTTP equivalent
                grpc_status = -1  # Default to -1 if not found, which will map to 500 Server Error
                status_match = re.search(r"grpc_status:(\d+)", error_text)
                if status_match:
                    grpc_status = int(status_match.group(1))

                http_status, reason = grpc_to_http.get(
                    grpc_status, (500, "Server Error")
                )

                return ParsedError(
                    status=http_status,
                    reason=reason,
                    detail=user_message,
                    body=error_text
                    if len(error_text) < 500
                    else error_text[:500] + "...",
                )

        current = getattr(current, "__cause__", None)

    return None


def parse_exception(exception: Exception) -> ParsedError | None:
    """Parse any exception to extract structured error information.

    Tries ApiException parsing first, then gRPC/Flight error parsing.

    Args:
        exception: The exception to parse

    Returns:
        ParsedError with extracted information, or None if parsing failed
    """
    # Try ApiException first
    parsed = parse_api_exception(exception)
    if parsed:
        return parsed

    # Try gRPC/Flight error parsing
    parsed = parse_grpc_error(exception)
    if parsed:
        return parsed

    return None


def get_error_suggestion(status: int) -> str:
    """Get a helpful suggestion for common HTTP status codes.

    Args:
        status: HTTP status code

    Returns:
        Suggestion string, or None if no specific suggestion available
    """
    suggestions = {
        400: "Check your input parameters and try again.",
        401: "Authentication failed. Run 'ax config init' to configure credentials.",
        403: "You don't have permission. Check your API key or space access.",
        404: "Resource not found. Verify the ID exists using the list command.",
        409: "Resource already exists. Choose a different name or use the list command.",
        422: "Validation failed. Check the error details for specific field issues.",
        429: "Rate limit exceeded. Wait a moment and try again.",
        500: "Server error. Try again later or contact support if the issue persists.",
        502: "Bad gateway. The server is temporarily unavailable. Try again later.",
        503: "Service unavailable. The server is temporarily down. Try again later.",
        504: "Gateway timeout. The server took too long to respond. Try again later.",
    }

    return suggestions.get(status, "")


def format_error_message(
    parsed_error: ParsedError, verbose: bool = False
) -> str:
    """Format an error message for display.

    Args:
        message: The base error message (e.g., "Failed to create dataset")
        parsed_error: Parsed API error information, or None for non-API errors
        verbose: Whether to show verbose technical details

    Returns:
        Formatted error message string with Rich markup
    """
    if verbose:
        return _format_verbose_error(parsed_error)

    return _format_clean_error(parsed_error)


def _format_clean_error(error: ParsedError) -> str:
    """Format error in clean, user-friendly mode."""
    lines = []

    # Add status and detail on one line if possible
    status_line_parts = []
    if error.status and error.reason:
        status_line_parts.append(f"{error.status} {error.reason}")

    # Prefer detail over title as it's more specific
    detail_text = error.detail or error.title
    if detail_text:
        if status_line_parts:
            status_line_parts.append(detail_text)
        else:
            status_line_parts.append(detail_text)

    if status_line_parts:
        lines.append("; ".join(status_line_parts))

    # Add helpful suggestion
    status = error.status if error.status else 0
    suggestion = get_error_suggestion(status)
    if suggestion:
        lines.append("")
        lines.append(f"  [dim]Suggestion: {suggestion}[/dim]")

    # Add verbose hint
    lines.append("  [dim]Run with --verbose for technical details.[/dim]")

    return "\n".join(lines)


def _format_verbose_error(error: ParsedError) -> str:
    """Format error in verbose mode with full technical details."""
    lines = [""]

    # HTTP Response section
    lines.append("[bold]HTTP Response:[/bold]")
    if error.status and error.reason:
        lines.append(f"  Status: {error.status} {error.reason}")
    if error.title:
        lines.append(f"  Title: {error.title}")
    if error.detail:
        lines.append(f"  Detail: {error.detail}")
    if error.type:
        lines.append(f"  Type: {error.type}")
    if error.instance:
        lines.append(f"  Instance: {error.instance}")

    # Response Headers section
    if error.headers:
        lines.append("")
        lines.append("[bold]Response Headers:[/bold]")
        # Show relevant headers (filter out verbose ones)
        relevant_headers = [
            "content-type",
            "x-request-id",
            "x-trace-id",
            "retry-after",
        ]
        for key, value in error.headers.items():
            # Show all headers that start with x- or are in relevant list
            if key.lower() in relevant_headers or key.lower().startswith("x-"):
                lines.append(f"  {key}: {value}")

    # Raw Response Body section
    if error.body:
        lines.append("")
        lines.append("[bold]Raw Response Body:[/bold]")
        # Truncate very long bodies
        body = error.body
        if len(body) > 1000:
            body = body[:1000] + "... (truncated)"
        # Indent body lines
        lines.extend(f"  {line}" for line in body.split("\n"))

    # Add suggestion at the end in verbose mode too
    status = error.status if error.status else 0
    suggestion = get_error_suggestion(status)
    if suggestion:
        lines.append("")
        lines.append(f"[dim]Suggestion: {suggestion}[/dim]")

    return "\n".join(lines)


def is_verbose_mode() -> bool:
    """Check if verbose mode is enabled via command-line flags.

    Returns:
        True if --verbose or -v flag is present in sys.argv
    """
    return "--verbose" in sys.argv or "-v" in sys.argv
