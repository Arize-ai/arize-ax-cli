<p align="center">
  <a href="https://arize.com/ax">
    <img src="https://storage.googleapis.com/arize-assets/arize-logo-white.jpg" width="600" />
  </a>
  <br/>
  <a target="_blank" href="https://pypi.org/project/arize-ax-cli/">
    <img src="https://img.shields.io/pypi/v/arize-ax-cli?color=blue">
  </a>
  <a target="_blank" href="https://pypi.org/project/arize-ax-cli/">
      <img src="https://img.shields.io/pypi/pyversions/arize-ax-cli">
  </a>
  <a target="_blank" href="https://arize-ai.slack.com/join/shared_invite/zt-2w57bhem8-hq24MB6u7yE_ZF_ilOYSBw#/shared-invite/email">
    <img src="https://img.shields.io/badge/slack-@arize-blue.svg?logo=slack">
  </a>
</p>

---

# Arize AX CLI <!-- omit in toc -->

- [Features](#features)
- [Installation](#installation)
  - [Using pip](#using-pip)
  - [From source](#from-source)
  - [Verify Installation](#verify-installation)
- [Quick Start](#quick-start)
  - [1. Initialize Configuration](#1-initialize-configuration)
  - [2. Verify Configuration](#2-verify-configuration)
  - [3. Start Using the CLI](#3-start-using-the-cli)
- [Configuration](#configuration)
  - [Configuration Commands](#configuration-commands)
  - [Configuration Modes](#configuration-modes)
    - [Simple Configuration (Recommended)](#simple-configuration-recommended)
    - [Advanced Configuration](#advanced-configuration)
  - [Configuration File Location](#configuration-file-location)
  - [Configuration Reference](#configuration-reference)
    - [All Available Sections](#all-available-sections)
  - [Using Environment Variables](#using-environment-variables)
    - [1. Auto-Detection During Setup](#1-auto-detection-during-setup)
    - [2. Manual Environment Variable References](#2-manual-environment-variable-references)
    - [Viewing Expanded Values](#viewing-expanded-values)
  - [Multiple Profiles](#multiple-profiles)
- [Shell Autocompletion](#shell-autocompletion)
  - [Quick Install (Recommended)](#quick-install-recommended)
  - [Verify Installation](#verify-installation-1)
  - [Manual Installation (Alternative)](#manual-installation-alternative)
  - [Supported Shells](#supported-shells)
- [Commands](#commands)
  - [Datasets](#datasets)
  - [Projects](#projects)
  - [Cache](#cache)
  - [Global Options](#global-options)
- [Usage Examples](#usage-examples)
  - [Creating a Dataset from a CSV File](#creating-a-dataset-from-a-csv-file)
  - [Exporting Dataset List to JSON](#exporting-dataset-list-to-json)
  - [Exporting Dataset Examples to Parquet](#exporting-dataset-examples-to-parquet)
  - [Using a Different Profile for a Command](#using-a-different-profile-for-a-command)
  - [Pagination](#pagination)
  - [Working with Multiple Environments](#working-with-multiple-environments)
- [Advanced Topics](#advanced-topics)
  - [Output Formats](#output-formats)
  - [Programmatic Usage](#programmatic-usage)
  - [Environment Variables](#environment-variables)
  - [Debugging](#debugging)
- [Troubleshooting](#troubleshooting)
  - [Configuration Issues](#configuration-issues)
  - [Connection Issues](#connection-issues)
  - [Shell Completion Not Working](#shell-completion-not-working)
- [Getting Help](#getting-help)
  - [Command-specific Help](#command-specific-help)
  - [Support](#support)
- [Contributing](#contributing)
- [License](#license)
- [Changelog](#changelog)

Official command-line interface for [Arize AI](https://arize.com) - streamline your MLOps workflows with datasets, experiments, projects, and more.

[![PyPI version](https://badge.fury.io/py/arize-ax-cli.svg)](https://badge.fury.io/py/arize-ax-cli)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

## Features

- **Dataset Management**: Create, list, update, and delete datasets
- **Project Management**: Organize your ML projects
- **Multiple Profiles**: Switch between different Arize environments
- **Flexible Output**: Export to JSON, CSV, Parquet, or display as tables
- **Shell Completion**: Tab completion for bash, zsh, and fish
- **Rich CLI Experience**: Beautiful terminal output with progress indicators

## Installation

### Using pip

```bash
pip install arize-ax-cli
```

### From source

```bash
git clone https://github.com/Arize-ai/arize-ax-cli.git
cd ax-cli
pip install -e .
```

### Verify Installation

```bash
ax --version
```

## Quick Start

### 1. Initialize Configuration

The first time you use the CLI, you'll need to create a _configuration profile_:

```bash
ax config init
```

This interactive setup will:

- Detect existing `ARIZE_*` environment variables and offer to use them
- Guide you through credential setup if no environment variables are found
- Create a configuration profile (default or named)
- Save your preferences for output format, caching, and more

**Example output:**

```
     _         _                 _   __  __
    / \   _ __(_)_______        / \  \ \/ /
   / _ \ | '__| |_  / _ \      / _ \  \  /
  / ___ \| |  | |/ /  __/     / ___ \ /  \
 /_/   \_\_|  |_/___\___|    /_/   \_\_/\_\
                  AI Observability Platform

Welcome to Arize AX CLI!
No configuration found. Let's set it up!

Environment Variable Detection

  ✓ Detected ARIZE_API_KEY = ak_***************xyz

Create config from detected environment variables? [Y/n]: y

Configuration saved to profile 'default'

You're ready to go! Try: ax datasets list
```

### 2. Verify Configuration

Check your configuration:

```bash
ax config show
```

### 3. Start Using the CLI

List your datasets:

```bash
ax datasets list
```

List your projects:

```bash
ax projects list
```

## Configuration

The Arize CLI uses a flexible configuration system that supports multiple profiles, environment variables, and two setup modes.

### Configuration Commands

| Command                      | Description                                      |
| ---------------------------- | ------------------------------------------------ |
| `ax config init`             | Create a new configuration profile interactively |
| `ax config list`             | List all available profiles                      |
| `ax config show`             | Display the current profile's configuration      |
| `ax config use <profile>`    | Switch to a different profile                    |
| `ax config delete <profile>` | Delete a configuration profile                   |

### Configuration Modes

When you run `ax config init`, you'll be prompted to choose between two configuration modes:

#### Simple Configuration (Recommended)

**Best for:** Most users, cloud deployments, standard Arize usage

The simple setup only asks for the essentials:

- **API Key**: Your Arize API key
- **Region**: US, EU, or leave unset (auto-detect)
- **Output Format**: table, json, csv, or parquet

**Example:**

```
Choose configuration mode:
> Simple (recommended)
  Advanced

API Key: Insert value
API Key (e.g., ak-123...): [hidden input]

Region:
> (leave empty for unset)
  US
  EU
  Use environment variable

Default output format:
> table
  json
  csv
  parquet
```

**Generated configuration:**

```toml
[profile]
name = "default"

[auth]
api_key = "ak_your_api_key_here"

[routing]
region = "US"

[output]
format = "table"
```

#### Advanced Configuration

**Best for:** On-premise deployments, Private Connect, custom routing, performance tuning

The advanced setup provides full control over:

1. **API Key**: Your Arize credentials
2. **Routing**: Choose from multiple strategies:
   - No override (use defaults)
   - Region-based routing (US, EU)
   - Single endpoint (on-premise deployments)
   - Base domain (Private Connect)
   - Custom endpoints & ports (granular control)
3. **Transport**: Performance tuning:
   - Stream max workers
   - Stream max queue bound
   - PyArrow max chunksize
   - Max HTTP payload size
4. **Security**: TLS certificate verification
5. **Output Format**: Default display format

**Example routing options:**

```
What type of override should we setup?
  0 - No override (use defaults)
  1 - Region (for region-based routing)
  2 - Single endpoint (typical for on-prem deployments)
> 3 - Base Domain (for Private Connect)
  4 - Custom endpoints & ports
```

**Generated configuration (example with Private Connect):**

```toml
[profile]
name = "production"

[auth]
api_key = "${ARIZE_API_KEY}"

[routing]
base_domain = "arize-private.yourcompany.com"

[transport]
stream_max_workers = 8
stream_max_queue_bound = 5000
pyarrow_max_chunksize = 10000
max_http_payload_size_mb = 8

[security]
request_verify = true

[storage]
directory = "~/.arize"
cache_enabled = true

[output]
format = "json"
```

### Configuration File Location

Configuration files are stored at:

- **Linux/macOS**: `~/.arize/config/<profile>.toml`
- **Windows**: `%USERPROFILE%\.arize\config\<profile>.toml`

### Configuration Reference

#### All Available Sections

**Authentication** (required)

```toml
[auth]
api_key = "ak_your_api_key_here"
# Or use environment variable reference:
api_key = "${ARIZE_API_KEY}"
```

**Routing** (choose one strategy)

```toml
[routing]
# Option 1: Region-based (recommended for cloud)
region = "US"  # or "EU"

# Option 2: Single endpoint (on-premise)
single_host = "arize.yourcompany.com"
single_port = "443"

# Option 3: Base domain (Private Connect)
base_domain = "arize-private.yourcompany.com"

# Option 4: Custom endpoints (advanced)
api_host = "api.arize.com"
api_scheme = "https"
otlp_host = "otlp.arize.com"
otlp_scheme = "https"
flight_host = "flight.arize.com"
flight_port = "443"
flight_scheme = "grpc+tls"
```

**Transport** (optional, advanced only)

```toml
[transport]
stream_max_workers = 8
stream_max_queue_bound = 5000
pyarrow_max_chunksize = 10000
max_http_payload_size_mb = 8
```

**Security** (optional, advanced only)

```toml
[security]
request_verify = true  # Set to false to disable SSL verification (not recommended)
```

**Storage** (optional)

```toml
[storage]
directory = "~/.arize"
cache_enabled = true
```

**Output** (optional)

```toml
[output]
format = "table"  # Options: table, json, csv, parquet
```

### Using Environment Variables

The CLI can detect and use environment variables in two ways:

#### 1. Auto-Detection During Setup

When you run `ax config init`, the CLI automatically detects existing `ARIZE_*` environment variables and offers to use them:

```bash
ax config init
```

```
Environment Variable Detection

  ✓ Detected ARIZE_API_KEY = ak_***************xyz
  ✓ Detected ARIZE_REGION = US

Create config from detected environment variables? [Y/n]: y
```

This will create a configuration that references the environment variables:

```toml
[auth]
api_key = "${ARIZE_API_KEY}"

[routing]
region = "${ARIZE_REGION}"
```

#### 2. Manual Environment Variable References

During both Simple and Advanced setup, you can choose "Use environment variable" for any field to reference an environment variable:

```
API Key:
  Insert value
> Use environment variable

Environment variable name for API Key: ARIZE_API_KEY
```

#### Viewing Expanded Values

To see the actual values (with environment variables expanded):

```bash
ax config show --expand
```

Without `--expand`, you'll see the variable references like `${ARIZE_API_KEY}`.

### Multiple Profiles

Create different profiles for different environments:

```bash
# Create a production profile
ax config init
# Enter profile name: production

# Create a staging profile
ax config init
# Enter profile name: staging

# List all profiles
ax config list

# Switch profiles
ax config use production
ax config use staging

# Use a specific profile for a single command
ax datasets list --profile production
```

## Shell Autocompletion

Enable tab completion for your shell to autocomplete commands, options, and arguments.

### Quick Install (Recommended)

The CLI includes a built-in installer that automatically configures completion for your shell:

```bash
ax --install-completion
```

This will:

- Detect your current shell (bash, zsh, or fish)
- Install the appropriate completion script
- Show you instructions to activate it

After running the command, restart your shell or open a new terminal window for the changes to take effect.

### Verify Installation

Once installed, test tab completion:

```bash
ax <TAB>         # Shows available commands (datasets, projects, config, cache)
ax datasets <TAB> # Shows dataset subcommands (list, get, create, delete)
ax datasets list --<TAB>  # Shows available options
```

### Manual Installation (Alternative)

If you prefer to see or customize the completion script before installing:

```bash
# View the completion script for your shell
ax --show-completion

# Save it to a file and source it manually
ax --show-completion >> ~/.bashrc  # For bash
ax --show-completion >> ~/.zshrc   # For zsh
```

### Supported Shells

- **Bash** (Linux, macOS, Windows Git Bash)
- **Zsh** (macOS default, Oh My Zsh)
- **Fish** (Linux, macOS)
- **PowerShell** (Windows)

## Commands

### Datasets

Manage your ML datasets:

```bash
# List datasets
ax datasets list --space-id <space-id> [--limit 15] [--cursor <cursor>]

# Get a specific dataset
ax datasets get <dataset-id>

# Create a new dataset
ax datasets create --name "My Dataset" --space-id <space-id> --file data.csv

# List examples from a dataset
ax datasets list_examples <dataset-id> [--version-id <version-id>] [--limit 30]

# Delete a dataset
ax datasets delete <dataset-id> [--force]
```

**Supported data file formats:**

- CSV (`.csv`)
- JSON (`.json`)
- JSON Lines (`.jsonl`)
- Parquet (`.parquet`)

### Projects

Organize your ML projects:

```bash
# List projects
ax projects list --space-id <space-id> [--limit 15] [--cursor <cursor>]

# Get a specific project
ax projects get <project-id>

# Create a new project
ax projects create --name "My Project" --space-id <space-id>

# Delete a project
ax projects delete <project-id> [--force]
```

### Cache

Manage the local cache:

```bash
# Clear the cache
ax cache clear
```

### Global Options

Available for all commands:

- `--profile, -p <name>`: Use a specific configuration profile
- `--output, -o <format>`: Set output format (`table`, `json`, `csv`, `parquet`, or a file path)
- `--verbose, -v`: Enable verbose logging
- `--help, -h`: Show help message

## Usage Examples

### Creating a Dataset from a CSV File

```bash
ax datasets create \
  --name "Customer Churn Dataset" \
  --space-id sp_abc123 \
  --file ./data/churn.csv
```

### Exporting Dataset List to JSON

```bash
ax datasets list --space-id sp_abc123 --output json > datasets.json
```

### Exporting Dataset Examples to Parquet

```bash
ax datasets list_examples ds_xyz789 --output examples.parquet
```

### Using a Different Profile for a Command

```bash
ax datasets list --space-id sp_abc123 --profile production
```

### Pagination

List more datasets using pagination:

```bash
# First page
ax datasets list --space-id sp_abc123 --limit 20

# Next page (use cursor from previous response)
ax datasets list --space-id sp_abc123 --limit 20 --cursor <cursor-value>
```

### Working with Multiple Environments

```bash
# Setup profiles for different environments
ax config init  # Create "production" profile
ax config init  # Create "staging" profile

# Switch contexts
ax config use production
ax datasets list --space-id sp_prod123

ax config use staging
ax datasets list --space-id sp_stage456
```

## Advanced Topics

### Output Formats

The CLI supports multiple output formats:

1. **Table** (default): Human-readable table format
2. **JSON**: Machine-readable JSON
3. **CSV**: Comma-separated values
4. **Parquet**: Apache Parquet columnar format

Set default format in config:

```bash
ax config init  # Select output format during setup
```

Or override per command:

```bash
ax datasets list --output json
ax datasets list --output datasets.csv
ax datasets list --output datasets.parquet
```

### Programmatic Usage

Integrate with scripts:

```bash
#!/bin/bash

# Export datasets to JSON
DATASETS=$(ax datasets list --space-id sp_abc123 --output json)

# Process with jq
echo "$DATASETS" | jq '.data[] | select(.name | contains("test"))'

# Export to file
ax datasets list_examples ds_xyz789 --output data.parquet
```

### Environment Variables

The CLI respects these environment variables:

- `ARIZE_API_KEY`: Your Arize API key
- `ARIZE_REGION`: Region (US, EU, etc.)
- Any other `ARIZE_*` variables will be detected during `ax config init`

### Debugging

Enable verbose mode to see detailed SDK logs:

```bash
ax datasets list --space-id sp_abc123 --verbose
```

## Troubleshooting

### Configuration Issues

**Problem**: `Config file not found`

**Solution**: Run `ax config init` to create a configuration profile.

---

**Problem**: `Invalid API key`

**Solution**: Verify your API key:

1. Check your configuration: `ax config show`
2. Regenerate your API key from the Arize UI
3. Update your config: `ax config init` (overwrite existing)

---

### Connection Issues

**Problem**: `Connection refused` or `SSL errors`

**Solution**:

1. Check your routing configuration: `ax config show`
2. Verify network connectivity
3. For on-premise installations, ensure `single_host` is configured correctly
4. For SSL issues, check `security.request_verify` setting (use with caution)

---

### Shell Completion Not Working

**Problem**: Tab completion doesn't work

**Solution**:

1. Verify completion is installed: Run the installation command for your shell
2. Reload your shell or open a new terminal
3. Ensure `ax` is in your PATH: `which ax`

---

## Getting Help

### Command-specific Help

Every command has detailed help:

```bash
ax --help
ax datasets --help
ax datasets create --help
ax config --help
```

### Support

- **Documentation**: [https://docs.arize.com/cli](https://docs.arize.com/cli)
- **Bug Reports**: [GitHub Issues](https://github.com/Arize-ai/ax-cli/issues)
- **Community**: [Arize Community Slack](https://arize-ai.slack.com)
- **Email**: [support@arize.com](mailto:support@arize.com)

## Contributing

We welcome contributions!

- **For developers**: See [DEVELOPMENT.md](DEVELOPMENT.md) for architecture, code structure, and development guide
- **For contributors**: See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines (coming soon)

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for release notes and version history.

---

**Built with ❤️ by [Arize AI](https://arize.com)**
