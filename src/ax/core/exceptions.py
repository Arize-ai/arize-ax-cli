"""Custom exceptions for the ax CLI."""


class AxError(Exception):
    """Base exception for all ax CLI errors."""

    exit_code = 1


class UsageError(AxError):
    """Invalid usage or arguments."""

    exit_code = 2


class AuthenticationError(AxError):
    """Authentication failed."""

    exit_code = 3


class APIError(AxError):
    """API request failed."""

    exit_code = 4


class BatchUploadError(APIError):
    """A batched upload failed, possibly after uploading part of the payload.

    Carries how much of the payload landed before the failure so commands can
    tell the user exactly where to resume instead of leaving them to guess.
    """

    def __init__(
        self,
        message: str,
        *,
        uploaded: int = 0,
        total: int = 0,
    ) -> None:
        """Record the failure message alongside the partial-upload counts."""
        super().__init__(message)
        self.uploaded = uploaded
        self.total = total


class FileIOError(AxError):
    """File I/O operation failed."""

    exit_code = 5


class ConfigError(AxError):
    """Configuration error."""

    exit_code = 1


class InvalidClientError(AxError):
    """Invalid Arize client configuration."""

    exit_code = 2
