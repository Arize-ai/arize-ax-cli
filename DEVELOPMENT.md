# Development Guide <!-- omit in toc -->

This guide explains the architecture, code structure, and conventions of the Arize AX CLI to help you onboard quickly and start contributing.

- [Architecture Overview](#architecture-overview)
- [Project Structure](#project-structure)
- [Core Concepts](#core-concepts)
  - [1. Command Structure](#1-command-structure)
  - [2. Error Handling](#2-error-handling)
  - [3. Output Formatting](#3-output-formatting)
  - [4. Configuration System](#4-configuration-system)
- [Module Reference](#module-reference)
  - [`src/ax/cli.py`](#srcaxclipy)
  - [`src/ax/commands/`](#srcaxcommands)
  - [`src/ax/config/`](#srcaxconfig)
  - [`src/ax/core/`](#srcaxcore)
    - [`decorators.py`](#decoratorspy)
    - [`exceptions.py`](#exceptionspy)
    - [`output.py`](#outputpy)
    - [`pydantic.py`](#pydanticpy)
    - [`error_formatter.py`](#error_formatterpy)
  - [`src/ax/utils/`](#srcaxutils)
    - [`console.py`](#consolepy)
    - [`file_io.py`](#file_iopy)
  - [`src/ax/ascii_art.py`](#srcaxascii_artpy)
- [Adding New Features](#adding-new-features)
  - [Adding a New Command](#adding-a-new-command)
  - [Adding a New Output Format](#adding-a-new-output-format)
  - [Adding Configuration Options](#adding-configuration-options)
- [Error Handling](#error-handling)
  - [Best Practices](#best-practices)
  - [Exit Codes](#exit-codes)
- [Output Formatting](#output-formatting)
  - [Format Selection Logic](#format-selection-logic)
  - [Working with Pydantic Models](#working-with-pydantic-models)
- [Configuration System](#configuration-system)
  - [Configuration Hierarchy](#configuration-hierarchy)
  - [Configuration Modes](#configuration-modes)
  - [Environment Variable References](#environment-variable-references)
- [Testing](#testing)
  - [Available Tasks](#available-tasks)
  - [Running Tests](#running-tests)
  - [Test Structure](#test-structure)
- [Code Style](#code-style)
  - [Formatting and Linting](#formatting-and-linting)
  - [Type Checking](#type-checking)
  - [Documentation](#documentation)
- [Resources](#resources)
- [Getting Help](#getting-help)

## Architecture Overview

The Arize AX CLI follows a layered architecture:

```
┌─────────────────────────────────────────────────┐
│         CLI Layer (Typer)                       │  ← Main app, command routing
├─────────────────────────────────────────────────┤
│       Commands (datasets, projects, config)     │  ← Command implementations
├─────────────────────────────────────────────────┤
│    Core (errors, output, decorators)            │  ← CLI business logic
├─────────────────────────────────────────────────┤
│    Utils (console, file I/O)                    │  ← Low-level helpers
├─────────────────────────────────────────────────┤
│    Config (schema, manager, setup)              │  ← Configuration system
├─────────────────────────────────────────────────┤
│     Arize SDK (ArizeClient)                     │  ← API communication
└─────────────────────────────────────────────────┘
```

**Layer Responsibilities:**

- **CLI Layer**: Application entry point, registers commands, handles global flags
- **Commands Layer**: Implements user-facing commands (datasets, projects, config, cache)
- **Core Layer**: CLI-specific business logic (error handling, output formatting, data transformation)
- **Utils Layer**: Generic, reusable helpers (console output, file operations)
- **Config Layer**: Configuration management system (profiles, schemas, interactive setup)
- **SDK Layer**: Arize SDK for API communication with the backend

**Key Distinction:**
- **Core (`src/ax/core/`)**: Application-specific logic tied to CLI operations (e.g., `@handle_errors` decorator, output formatters, exception classes)
- **Utils (`src/ax/utils/`)**: Generic utilities that could work in any Python application (e.g., `success()`, `read_data_file()`)

**Key Principles:**
- **Separation of Concerns**: Each layer has a specific responsibility
- **Consistent Error Handling**: All commands use `@handle_errors` decorator
- **Flexible Output**: Support for multiple output formats (table, JSON, CSV, Parquet)
- **Rich Terminal UI**: Beautiful console output using Rich library

## Project Structure

```
arize-ax-cli/
├── src/ax/
│   ├── __init__.py           # Package initialization
│   ├── __main__.py           # Entry point for python -m ax
│   ├── cli.py                # Main CLI app and command registration
│   ├── version.py            # Version string
│   ├── ascii_art.py          # ASCII art banners for welcome screen
│   │
│   ├── commands/             # Command implementations
│   │   ├── __init__.py
│   │   ├── cache.py          # Cache management commands
│   │   ├── config.py         # Configuration commands
│   │   ├── datasets.py       # Dataset CRUD operations
│   │   └── projects.py       # Project CRUD operations
│   │
│   ├── config/               # Configuration management
│   │   ├── __init__.py
│   │   ├── schema.py         # Pydantic models for config
│   │   ├── manager.py        # Config CRUD operations
│   │   ├── setup.py          # Interactive setup flows
│   │   └── input_readers.py  # User input prompts
│   │
│   ├── core/                 # Core utilities
│   │   ├── __init__.py
│   │   ├── decorators.py     # @handle_errors decorator
│   │   ├── exceptions.py     # Custom exception classes
│   │   ├── output.py         # Output formatters (table, JSON, CSV, Parquet)
│   │   ├── pydantic.py # Pydantic model utilities
│   │   └── error_formatter.py # Error message formatting
│   │
│   └── utils/                # Utility functions
│       ├── __init__.py
│       ├── console.py        # Console helpers (success, error, spinner)
│       └── file_io.py        # File I/O operations
│
├── tests/                    # Test suite
├── pyproject.toml           # Project metadata and dependencies
├── README.md                # User documentation
└── DEVELOPMENT.md           # This file
```

## Core Concepts

### 1. Command Structure

Every command follows this pattern:

```python
from typing import Annotated
import typer
from ax.core.decorators import handle_errors
from ax.config.manager import ConfigManager
from ax.utils.console import success, spinner

@app.command("list")
@handle_errors
def list_items(
    profile: Annotated[
        str,
        typer.Option("--profile", "-p", help="Configuration profile to use"),
    ] = "",
    output: Annotated[
        str,
        typer.Option("--output", "-o", help="Output format or file path"),
    ] = "",
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose logs"),
    ] = False,
) -> None:
    """List items with optional filters."""
    # 1. Load config
    config = ConfigManager.load(profile, expand_env_vars=True)

    # 2. Create SDK client
    client = ArizeClient(**asdict(config.to_sdk_config()))

    # 3. Parse output options
    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    # 4. Make API call with spinner
    try:
        with spinner("Fetching items"):
            response = client.items.list()
    except Exception as e:
        raise APIError(f"Failed to list items: {e}") from e

    # 5. Output results
    output_data(response, format_type=output_format, output_file=output_file)
```

### 2. Error Handling

All commands MUST use the `@handle_errors` decorator:

```python
from ax.core.decorators import handle_errors
from ax.core.exceptions import APIError, ConfigError

@app.command("example")
@handle_errors
def example_command() -> None:
    """Example command."""
    # Decorator catches all exceptions and formats them nicely
    # Raise custom exceptions with meaningful messages
    if something_wrong:
        raise APIError("Failed to fetch data from API")
```

**Exception Hierarchy:**
- `AxError` - Base exception (exit code 1)
  - `UsageError` - Invalid arguments (exit code 2)
  - `AuthenticationError` - Auth failed (exit code 3)
  - `APIError` - API request failed (exit code 4)
  - `FileIOError` - File operation failed (exit code 5)
  - `ConfigError` - Configuration error (exit code 1)

### 3. Output Formatting

The CLI supports multiple output formats:

```python
from ax.core.output import output_data

# Automatic format selection based on user preference
output_data(
    data=response,           # Pydantic BaseModel
    format_type="table",     # table, json, csv, parquet
    output_file="data.csv",  # Optional file path
)
```

**Available Formatters:**
- `TableFormatter` - Rich terminal tables (stdout only)
- `JSONFormatter` - JSON with indentation
- `CSVFormatter` - CSV for spreadsheets
- `ParquetFormatter` - Parquet for data analysis (requires file path)

### 4. Configuration System

Configuration is managed through TOML files stored in `~/.arize/config/`:

```python
from ax.config.manager import ConfigManager
from ax.config.schema import Config

# Load config (expands environment variables)
config = ConfigManager.load(profile="default", expand_env_vars=True)

# Save config
ConfigManager.save(config, profile="default")

# List all profiles
profiles = ConfigManager.list_profiles()

# Switch active profile
ConfigManager.set_active_profile("production")
```

## Module Reference

### `src/ax/cli.py`
**Purpose:** Main CLI application entry point

**Key Functions:**
- `app = typer.Typer(...)` - Main Typer app
- `register_commands()` - Registers all command groups
- `main()` - Global callback for flags like `--verbose`

**Usage:**
```python
# Commands are registered here
from ax.commands.datasets import app as datasets_app
app.add_typer(datasets_app, name="datasets")
```

### `src/ax/commands/`
**Purpose:** Command implementations for different resources

**Structure:**
- Each module defines a Typer sub-application
- Commands follow CRUD pattern: list, get, create, delete
- All commands decorated with `@handle_errors`

**Example - Adding a new command:**
```python
# src/ax/commands/experiments.py
import typer
from ax.core.decorators import handle_errors

app = typer.Typer(name="experiments", help="Manage experiments")

@app.command("list")
@handle_errors
def list_experiments() -> None:
    """List all experiments."""
    pass
```

Then register in `cli.py`:
```python
from ax.commands.experiments import app as experiments_app
app.add_typer(experiments_app, name="experiments", help="Manage experiments")
```

### `src/ax/config/`
**Purpose:** Configuration management system

**Key Modules:**
- `schema.py` - Pydantic models defining config structure
- `manager.py` - CRUD operations for config files
- `setup.py` - Interactive configuration setup (Simple vs Advanced)
- `input_readers.py` - Questionary-based user input prompts

**Adding a new config field:**
1. Add to `schema.py`:
   ```python
   class TransportConfig(BaseModel):
       new_field: int = Field(default=100, description="New setting")
   ```

2. Add input reader in `input_readers.py`:
   ```python
   def read_new_field() -> int:
       return questionary.text("New field:", default="100").ask()
   ```

3. Use in `setup.py` (Advanced mode):
   ```python
   transport_config = TransportConfig(
       new_field=read_new_field(),
   )
   ```

### `src/ax/core/`
**Purpose:** CLI-specific business logic and application-level utilities

Contains functionality that is specific to this CLI application's domain (error handling, output formatting, data transformations). These modules understand the CLI's requirements and SDK responses.

**Key Modules:**

#### `decorators.py`
Error handling decorator that wraps all commands:
```python
@handle_errors
def my_command():
    # Automatically catches and formats all exceptions
    pass
```

#### `exceptions.py`
Custom exception classes with exit codes:
```python
raise APIError("Failed to fetch data")  # Exit code 4
raise ConfigError("Invalid config")     # Exit code 1
```

#### `output.py`
Output formatting system:
```python
# Factory pattern for formatters
formatter = get_formatter("json")
formatter.format(data, output_file="data.json")

# Convenience function
output_data(data, format_type="table", output_file="")
```

#### `pydantic.py`
Utilities for working with Pydantic models:
- `basemodel_to_dataframe()` - Convert BaseModel to pandas DataFrame
- `flatten_basemodel_for_export()` - Flatten nested models for CSV/Parquet
- `categorize_basemodel_fields()` - Separate scalar vs list fields

#### `error_formatter.py`
Formats SDK exceptions into user-friendly messages with:
- Error type and message
- Request details (URL, method, headers)
- Response details (status, body)
- Suggestions for resolution

### `src/ax/utils/`
**Purpose:** Generic, reusable helper functions

Contains low-level utilities that are independent of the CLI's specific business logic. These could be used in any Python application (console I/O, file operations).

**Difference from Core:**
- **Core**: Knows about SDK responses, error types, output formats, CLI requirements
- **Utils**: Generic helpers with no CLI-specific knowledge

#### `console.py`
Console output helpers using Rich:
```python
from ax.utils.console import success, error, warning, info, spinner

success("Operation completed!")
error("Something went wrong")
warning("This is a warning")
info("Informational message")

with spinner("Loading data") as status:
    # Long operation
    status.update("Still loading...")
```

#### `file_io.py`
File I/O operations:
```python
from ax.utils.file_io import read_data_file, parse_output_option

# Read various file formats
df = read_data_file("data.csv")   # Supports CSV, JSON, JSONL, Parquet

# Parse output option (format or file path)
format_type, output_file = parse_output_option("data.json")
# Returns: ("json", "data.json")
```

### `src/ax/ascii_art.py`
**Purpose:** ASCII art banners for welcome screen

**Structure:**
- Contains 6 different banner options (OPTION_1 through OPTION_6)
- `DEFAULT_BANNER` variable points to the active banner
- Used in `config.py` during first-time setup

**Changing the banner:**
```python
# In ascii_art.py
DEFAULT_BANNER = OPTION_3  # Switch to a different design
```

## Adding New Features

### Adding a New Command

1. **Create command module** (or add to existing):
   ```python
   # src/ax/commands/experiments.py
   import typer
   from ax.core.decorators import handle_errors
   from ax.config.manager import ConfigManager

   app = typer.Typer(name="experiments", help="Manage experiments")

   @app.command("list")
   @handle_errors
   def list_experiments(
       profile: str = "",
       verbose: bool = False,
   ) -> None:
       """List all experiments."""
       config = ConfigManager.load(profile, expand_env_vars=True)
       # Implementation
   ```

2. **Register in `cli.py`**:
   ```python
   def register_commands() -> None:
       from ax.commands.experiments import app as experiments_app
       app.add_typer(experiments_app, name="experiments", help="Manage experiments")
   ```

3. **Update README** with new command documentation

### Adding a New Output Format

1. **Create formatter class** in `src/ax/core/output.py`:
   ```python
   class YAMLFormatter(OutputFormatter):
       """YAML formatter for configuration files."""

       def format(self, data: BaseModel, output_file: str = "") -> None:
           import yaml
           output = data.model_dump(mode="json", exclude_none=True)
           yaml_str = yaml.dump(output, default_flow_style=False)

           if output_file:
               Path(output_file).write_text(yaml_str)
           else:
               text(yaml_str)
   ```

2. **Register in factory**:
   ```python
   def get_formatter(format_type: str) -> OutputFormatter:
       formatters = {
           "table": TableFormatter,
           "json": JSONFormatter,
           "csv": CSVFormatter,
           "parquet": ParquetFormatter,
           "yaml": YAMLFormatter,  # Add here
       }
       # ...
   ```

3. **Update schema** in `src/ax/config/schema.py`:
   ```python
   class OutputConfig(BaseModel):
       format: Literal["table", "json", "csv", "parquet", "yaml"] = Field(default="table")
   ```

### Adding Configuration Options

1. **Update schema** in `src/ax/config/schema.py`:
   ```python
   class TransportConfig(BaseModel):
       stream_max_workers: int = Field(default=8)
       new_setting: str = Field(default="value")  # Add new field
   ```

2. **Add input reader** in `src/ax/config/input_readers.py`:
   ```python
   def read_new_setting() -> str:
       return questionary.text(
           "New setting:",
           default="value",
       ).ask()
   ```

3. **Update setup flow** in `src/ax/config/setup.py`:
   ```python
   def advanced_setup(profile: str) -> Config:
       transport_config = TransportConfig(
           stream_max_workers=read_int_field(...),
           new_setting=read_new_setting(),  # Add here
       )
       # ...
   ```

## Error Handling

### Best Practices

1. **Always use `@handle_errors` decorator** on command functions
2. **Raise specific exceptions** with clear messages:
   ```python
   # Good
   raise APIError("Failed to fetch dataset 'abc123': Not found")

   # Bad
   raise Exception("Error")
   ```

3. **Catch SDK exceptions** and re-raise as CLI exceptions:
   ```python
   try:
       dataset = client.datasets.get(dataset_id=id)
   except Exception as e:
       raise APIError(f"Failed to get dataset: {e}") from e
   ```

4. **Provide context** in error messages:
   ```python
   # Good - tells user what failed and why
   raise FileIOError(f"Failed to read file '{file_path}': {e}")

   # Bad - generic, unhelpful
   raise FileIOError("File error")
   ```

### Exit Codes

The CLI uses standard exit codes:
- `0` - Success
- `1` - General error (AxError, ConfigError)
- `2` - Usage error (UsageError)
- `3` - Authentication error (AuthenticationError)
- `4` - API error (APIError)
- `5` - File I/O error (FileIOError)
- `130` - Interrupted by user (Ctrl+C)

## Output Formatting

### Format Selection Logic

```python
from ax.utils.file_io import parse_output_option

# User provides format name
format_type, output_file = parse_output_option("json")
# Returns: ("json", "")

# User provides file path with extension
format_type, output_file = parse_output_option("data.csv")
# Returns: ("csv", "data.csv")

# Use config default if not specified
output = output_arg if output_arg else config.output.format
```

### Working with Pydantic Models

All API responses should be Pydantic BaseModels:

```python
from pydantic import BaseModel

class Dataset(BaseModel):
    id: str
    name: str
    created_at: datetime

# Output system automatically handles BaseModels
output_data(dataset, format_type="table")
```

For list responses with pagination:

```python
class ListDatasetsResponse(BaseModel):
    data: list[Dataset]
    pagination: PaginationInfo

    def to_df(self, **kwargs) -> pd.DataFrame:
        """Convert data items to DataFrame."""
        # Implementation
```

## Configuration System

### Configuration Hierarchy

1. **Environment variables** (highest priority)
   - `ARIZE_API_KEY`, `ARIZE_REGION`, etc.

2. **Profile-specific config**
   - `~/.arize/config/<profile>.toml`

3. **Default values**
   - Defined in `schema.py`

### Configuration Modes

**Simple Mode** (recommended for most users):
- API Key
- Region (US, EU, or unset)
- Output format

**Advanced Mode** (for on-premise, Private Connect):
- All Simple Mode options
- Custom routing (single endpoint, base domain, custom hosts)
- Transport settings (workers, queue size, chunk size)
- Security settings (TLS verification)

### Environment Variable References

Config files can reference environment variables:

```toml
[auth]
api_key = "${ARIZE_API_KEY}"

[routing]
region = "${ARIZE_REGION}"
```

These are expanded when loading config:
```python
config = ConfigManager.load(profile="default", expand_env_vars=True)
```

## Testing

We use [taskipy](https://github.com/taskipy/taskipy) to manage common development tasks. Taskipy provides a simple way to define and run project tasks.

### Available Tasks

| Task | Command | Description |
|------|---------|-------------|
| `task test` | `pytest --cov .` | Run tests with coverage |
| `task lint` | `ruff format . && ruff check --fix .` | Format code and fix linting issues |
| `task type-check` | `mypy --no-incremental --show-traceback ...` | Run type checking |

**CI-specific tasks** (used in continuous integration):
- `task ci-test` - Run tests with full coverage reports
- `task ci-lint` - Check linting (no auto-fix)
- `task ci-format` - Check formatting (no auto-fix)
- `task ci-type-check` - Run type checking

### Running Tests

**Using taskipy (recommended):**

```bash
# Run all tests with coverage
task test

# This runs: pytest --cov .
```

### Test Structure

```
tests/
├── conftest.py              # Pytest fixtures
├── test_commands/           # Command tests
│   ├── test_datasets.py
│   └── test_projects.py
├── test_config/             # Configuration tests
│   ├── test_manager.py
│   └── test_schema.py
└── test_core/               # Core utility tests
    ├── test_decorators.py
    └── test_output.py
```

## Code Style

### Formatting and Linting

We use [Ruff](https://github.com/astral-sh/ruff) for formatting and linting.

**Using taskipy (recommended):**

```bash
# Format and fix linting issues
task lint

# This runs: ruff format . && ruff check --fix .
```

### Type Checking

We use [mypy](https://mypy-lang.org/) for static type checking.

**Using taskipy (recommended):**

```bash
# Run type checking
task type-check

# This runs: mypy --no-incremental --show-traceback --config-file pyproject.toml .
```

### Documentation

All public functions must have docstrings:

```python
def my_function(arg1: str, arg2: int) -> bool:
    """Brief description of what the function does.

    Args:
        arg1: Description of arg1
        arg2: Description of arg2

    Returns:
        Description of return value

    Raises:
        APIError: When API request fails

    Example:
        >>> my_function("test", 42)
        True
    """
    pass
```

## Resources

- **Typer Documentation**: https://typer.tiangolo.com/
- **Rich Documentation**: https://rich.readthedocs.io/
- **Pydantic Documentation**: https://docs.pydantic.dev/
- **Arize SDK Documentation**: https://docs.arize.com/sdk
- **Python Type Hints**: https://docs.python.org/3/library/typing.html

## Getting Help

- **Issues**: https://github.com/Arize-ai/arize-ax-cli/issues
- **Discussions**: https://github.com/Arize-ai/arize-ax-cli/discussions
- **Slack**: https://arize-ai.slack.com

---

**Happy Coding!** If you have questions or suggestions for improving this guide, please open an issue or discussion.
