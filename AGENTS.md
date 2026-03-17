# AGENTS.md — Arize AX CLI

Command-line interface for the Arize AI platform (`ax` CLI, v0.3.x). Uses `uv` as the package manager, `ruff` for linting/formatting, `mypy` for type checking, and `pytest` for tests. All tooling is configured in `pyproject.toml` and invoked via `taskipy`.

For user-facing documentation see `DEVELOPMENT.md` (architecture, error handling, output formatting) and `README.md`.

## Key Structure

```
arize-ax-cli/
├── pyproject.toml                # All tool config (ruff, mypy, pytest, taskipy, coverage)
├── uv.lock                       # Dependency lock file — commit changes to this
├── src/ax/
│   ├── cli.py                    # Main Typer app + command group registration
│   ├── version.py                # __version__ string
│   ├── ascii_art.py              # Welcome screen banners
│   ├── commands/                 # One module per command group
│   │   ├── datasets.py           # ax datasets ...
│   │   ├── experiments.py        # ax experiments ...
│   │   ├── projects.py           # ax projects ...
│   │   ├── spans.py              # ax spans ...
│   │   ├── traces.py             # ax traces ...
│   │   ├── annotation_configs.py # ax annotation-configs ...
│   │   ├── profiles.py           # ax profiles ...
│   │   └── cache.py              # ax cache ...
│   ├── config/                   # Configuration system
│   │   ├── schema.py             # Pydantic models for TOML config
│   │   ├── manager.py            # Config CRUD (reads ~/.arize/config/ or profiles)
│   │   ├── setup.py              # Interactive setup flows
│   │   └── input_readers.py      # questionary-based prompts
│   ├── core/                     # CLI-specific cross-cutting concerns
│   │   ├── decorators.py         # @handle_errors — wrap commands for clean error output
│   │   ├── exceptions.py         # Custom exception hierarchy (8 types, exit codes 0–5, 130)
│   │   ├── output.py             # Output formatters (table, JSON, CSV, Parquet)
│   │   └── error_formatter.py    # SDK ApiException → friendly error messages
│   └── utils/                    # Generic utilities
│       ├── console.py            # Rich helpers (success, error, spinner)
│       ├── file_io.py            # File read/write
│       ├── projects.py           # Project utility functions
│       └── export.py             # Export helpers
├── tests/
│   ├── conftest.py               # Shared fixtures (temp_config_dir, mock_config_dir, etc.)
│   ├── commands/                 # Tests per command group
│   ├── config/                   # Config system tests
│   ├── core/                     # Core output/error tests
│   └── utils/                    # Utility tests
└── DEVELOPMENT.md                # Architecture guide, adding commands, error codes, output formats
```

## Development Commands

Run from `sdk/python/arize-ax-cli/`:

```bash
task lint         # ruff format + ruff check --fix (auto-corrects)
task type-check   # mypy static type analysis
task test         # pytest with branch coverage
```

**Always run `task lint`, `task type-check`, and `task test` after completing a significant feature or refactor.**

After making significant changes, run the `arize-code-review` subagent (`.agents/agents/arize-code-review.md`) for a staff-level review before presenting results.

CI-only variants (no auto-fix): `task ci-format`, `task ci-lint`, `task ci-type-check`, `task ci-test`.

## Conventions

- **Line length:** 80 chars (code), 110 chars (docstrings)
- **Docstrings:** Google-style required for public functions and classes
- **Imports:** Managed by ruff/isort — do not sort manually
- **Python version:** Requires >=3.11
- **Adding a new command group:**
  1. Create `src/ax/commands/<group>.py` with a `typer.Typer()` app
  2. Register it in `src/ax/cli.py`
  3. Decorate all command functions with `@handle_errors` from `core/decorators.py`
  4. Add tests under `tests/commands/`
- **Output:** Always use `core/output.py` formatters — never write directly to stdout. Supports table (default), JSON, CSV, Parquet via `--format` flag.
- **Errors:** Raise from the `core/exceptions.py` hierarchy so `@handle_errors` can map them to clean exit codes. Exit codes: 0 success, 1 API error, 2 config error, 3 validation error, 4 not found, 5 permission error, 130 keyboard interrupt.
- **Config:** User config lives in `~/.arize/config/` (default) or `~/.arize/profiles/<name>.toml`. Use `ConfigManager` from `config/manager.py` — never read config files directly.
- **Test markers:** `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.slow`
