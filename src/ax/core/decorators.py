"""Common decorators for CLI commands."""

import functools
import sys
from collections.abc import Callable
from typing import ParamSpec, TypeVar

import typer
from rich.console import Console

from ax.core.error_formatter import (
    format_error_message,
    is_verbose_mode,
    parse_exception,
)
from ax.core.exceptions import (
    AxError,
)
from ax.utils.console import error, new_line, warning

console = Console()

P = ParamSpec("P")
R = TypeVar("R")


def handle_errors(f: Callable[P, R]) -> Callable[P, R]:
    """Catch and format errors, exit with appropriate code.

    This decorator should wrap all command functions to provide
    consistent error handling and user-friendly error messages.
    """

    @functools.wraps(f)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return f(*args, **kwargs)
        except AxError as e:
            # Custom ax errors with exit codes
            # These errors are caught by the CLI and not unexpected, such as API
            # errors, validation errors, config errors, etc.

            # Try to parse any exception for better formatting
            parsed_error = parse_exception(e)

            if parsed_error:
                # Format with structured error information
                formatted_message = format_error_message(
                    parsed_error,
                    is_verbose_mode(),
                )
                error(formatted_message)
            else:
                # Fallback to simple formatting for non-API errors
                error(str(e))

            raise typer.Exit(code=e.exit_code) from e
        except typer.Exit:
            # Let Typer handle its own exits
            raise
        except KeyboardInterrupt:
            new_line()
            warning("Operation cancelled by user")
            raise typer.Exit(code=130) from None
        except Exception as e:
            # Unexpected errors
            if "--verbose" in sys.argv or "-v" in sys.argv:
                console.print_exception()
            else:
                console.print(f"[red]✗ Unexpected error: {e}[/red]")
                console.print("[dim]Run with --verbose for more details[/dim]")
            raise typer.Exit(code=1) from e

    return wrapper
