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


class MfaRequiredError(AuthenticationError):
    """A new browser sign-in is required to verify MFA."""


class APIError(AxError):
    """API request failed."""

    exit_code = 4


class APIResponseError(APIError):
    """API response could not be decoded."""


class FileIOError(AxError):
    """File I/O operation failed."""

    exit_code = 5


class ConfigError(AxError):
    """Configuration error."""

    exit_code = 1


class RoutingConfigError(ConfigError):
    """OAuth routing is invalid or cannot be resolved."""


class InvalidClientError(AxError):
    """Invalid Arize client configuration."""

    exit_code = 2
