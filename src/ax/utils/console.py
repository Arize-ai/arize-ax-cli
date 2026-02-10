"""Progress indicators and interactive features."""

import sys
from collections.abc import Generator
from contextlib import contextmanager

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

console = Console()


def confirm(message: str, default: bool = False, abort: bool = False) -> bool:
    """Prompt user for yes/no confirmation.

    Args:
        message: Confirmation message
        default: Default value if user just presses Enter
        abort: If True, abort on 'no' response

    Returns:
        True if user confirmed, False otherwise

    Example:
        >>> if confirm("Delete this dataset?", default=False):
        >>>     delete_dataset()
    """
    return typer.confirm(message, default=default, abort=abort)


def prompt(
    message: str,
    default: str | None = None,
    hide_input: bool = False,
    confirmation_prompt: bool = False,
) -> str:
    """Prompt user for text input.

    Args:
        message: Prompt message
        default: Default value if user just presses Enter
        hide_input: Hide user input (for passwords/secrets)
        confirmation_prompt: Ask user to enter value twice

    Returns:
        User input string

    Example:
        >>> api_key = prompt("API Key", hide_input=True)
        >>> name = prompt("Dataset name", default="my-dataset")
    """
    return typer.prompt(
        message,
        default=default,
        hide_input=hide_input,
        confirmation_prompt=confirmation_prompt,
    )


def success(message: str) -> None:
    """Print success message."""
    console.print(f"[green]✓ {message}[/green]")


def error(message: str) -> None:
    """Print error message."""
    console.print(f"[red] ✗ Error: {message}[/red]")


def warning(message: str) -> None:
    """Print warning message."""
    console.print(f"[yellow] ⚠ Warning: {message}[/yellow]")


def info(message: str) -> None:
    """Print info message."""
    console.print(f"[blue]ℹ {message}[/blue]")  # noqa: RUF001


def emphasis(message: str) -> None:
    """Print emphasis message."""
    console.print(f"[bold blue]{message}[/bold blue]")


def text(message: str) -> None:
    """Print emphasis message."""
    console.print(f"{message}")


def text_dimmed(message: str) -> None:
    """Print dimmed text message."""
    console.print(f"[dim]{message}[/dim]")


def text_bold(message: str) -> None:
    """Print bold text message."""
    console.print(f"[bold]{message}[/bold]")


def new_line() -> None:
    """Print a new line."""
    console.print()


def mask(val: str, num_visible: int = 6) -> str:
    """Mask a string value, showing only a portion of it."""
    N = round(num_visible / 2)
    return f"{val[: 2 + N]}...{val[-N:]}" if len(val) > N else "***"


@contextmanager
def spinner(
    message: str,
    success_msg: str = "",
    error_msg: str = "",
) -> Generator[object, None, None]:
    """Display live status that can be updated during operation.

    Context manager for multi-step operations where status message needs
    to change as operation progresses.

    Args:
        message: Initial status message
        success_msg: Message to display on success
        error_msg: Message to display on error

    Yields:
        Console: Console object for updating status

    Example:
        >>> with spinner("Initializing") as live:
        >>> # ... initialization ...
        >>>     live.update("Processing data")
        >>> # ... processing ...
        >>>     live.update("Finalizing")

    Notes:
        - Falls back to text output in non-TTY environments
        - Status automatically clears when context exits
    """
    # Check if we should show status
    if not sys.stderr.isatty():
        # Fallback to simple text output for non-interactive environments
        info(message)
        try:
            yield console
            if success_msg:
                success(success_msg)
        except Exception:
            if error_msg:
                error(error_msg)
            raise
        return

    # Show live status in interactive terminal
    with console.status(f"{message}...", spinner="dots") as status_obj:
        try:
            yield status_obj
            # Success case - show success message if provided
            if success_msg:
                success(success_msg)
        except Exception:
            # Error case - show error message if provided
            if error_msg:
                error(error_msg)
            # Re-raise exception so @handle_errors can catch it
            raise


@contextmanager
def progress_bar(
    total: int,
    description: str,
) -> Generator[object, None, None]:
    """Create progress bar with percentage for operations with known total.

    Context manager that yields a Rich Progress object for manual updates.
    Useful for operations that can report progress incrementally.

    Args:
        total: Total number of items to process
        description: Description of the operation

    Yields:
        Progress: Rich Progress object for updating progress

    Example:
        >>> with progress_bar(100, "Uploading batches") as progress:
        >>>     task = progress.add_task(description, total=total)
        >>>     for i in range(100):
        >>> # ... do work ...
        >>>         progress.update(task, advance=1)

    Notes:
        - Falls back to text output in non-TTY environments
        - Automatically handles cleanup on exceptions
        - Progress bar uses green color for filled portion
    """
    # Check if we should show progress bar
    if not sys.stderr.isatty():
        # Fallback to simple text output for non-interactive environments
        info(f"{description}...")

        # Create a dummy progress object that does nothing
        class DummyProgress:
            def add_task(self, *args: object, **kwargs: object) -> int:
                return 0

            def update(self, *args: object, **kwargs: object) -> None:
                pass

        yield DummyProgress()
        return

    # Show progress bar in interactive terminal
    progress = Progress(
        SpinnerColumn(spinner_name="dots", style="blue"),
        TextColumn("[blue]{task.description}"),
        BarColumn(complete_style="green", finished_style="green"),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    )
    with progress:
        yield progress
