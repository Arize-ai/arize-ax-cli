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
  - [Updating a Profile](#updating-a-profile)
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
  - [Global Options](#global-options)
  - [AI Integrations](#ai-integrations)
  - [Annotation Configs](#annotation-configs)
  - [Annotation Queues](#annotation-queues)
  - [API Keys](#api-keys)
  - [Cache](#cache)
  - [Datasets](#datasets)
  - [Evaluators](#evaluators)
    - [Code evaluators](#code-evaluators)
  - [Experiments](#experiments)
    - [`ax experiments run` — execute a task locally](#ax-experiments-run--execute-a-task-locally)
  - [Organizations](#organizations)
  - [Projects](#projects)
  - [Prompts](#prompts)
  - [Roles](#roles)
  - [Spaces](#spaces)
  - [Skills](#skills)
  - [Spans](#spans)
  - [Tasks](#tasks)
  - [Traces](#traces)
  - [Users](#users)
- [Usage Examples](#usage-examples)
  - [Creating a Dataset from a CSV File](#creating-a-dataset-from-a-csv-file)
  - [Creating a Dataset from stdin](#creating-a-dataset-from-stdin)
  - [Exporting Dataset List to JSON](#exporting-dataset-list-to-json)
  - [Exporting Dataset Examples](#exporting-dataset-examples)
  - [Running an Experiment with a Task](#running-an-experiment-with-a-task)
  - [Exporting Experiment Runs](#exporting-experiment-runs)
  - [Exporting Spans by Trace ID](#exporting-spans-by-trace-id)
  - [Exporting Spans](#exporting-spans)
  - [Listing Traces and Exporting to Parquet](#listing-traces-and-exporting-to-parquet)
  - [Pagination](#pagination)
  - [Working with Multiple Environments](#working-with-multiple-environments)
  - [Filtering Spans by Status](#filtering-spans-by-status)
  - [Listing Traces in a Time Window](#listing-traces-in-a-time-window)
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

Official command-line interface for [Arize AI](https://arize.com) - manage your AI observability resources including datasets, projects, spans, traces, and more.

[![PyPI version](https://badge.fury.io/py/arize-ax-cli.svg)](https://badge.fury.io/py/arize-ax-cli)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## Features

- **Dataset Management**: Create, list, update, and delete datasets
- **Evaluator Management**: Create and manage LLM-as-judge evaluators and their versions
- **Experiment Management**: Run and analyze experiments on your datasets
- **Project Management**: Organize your projects
- **API Key Management**: Create, refresh, and revoke API keys
- **AI Integrations**: Configure external LLM providers (OpenAI, Anthropic, AWS Bedrock, and more)
- **Prompt Management**: Create and version prompts with label management
- **Role Management**: Create, update, and delete custom roles with granular permissions
- **User Management**: Invite users, manage account-level roles, and control organization/space memberships
- **Agent Skills**: Install Arize context skills for AI coding agents (Claude Code, Cursor, Codex, Windsurf)
- **Spans & Traces**: Query and filter LLM spans and traces
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
cd arize-ax-cli
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
ax profiles create
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

  ✓ Detected ARIZE_API_KEY = ak-2a...FCf

Create config from detected environment variables? [Y/n]: y

? Default output format: table

✓ Configuration saved to profile 'default'

You're ready to go! Try: ax datasets list
```

### 2. Verify Configuration

Check your configuration:

```bash
ax profiles show
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

Export spans from a project:

```bash
ax spans export <project-id> --stdout
```

List traces in a project:

```bash
ax traces list <project-id>
```

## Configuration

The Arize CLI uses a flexible configuration system that supports multiple profiles, environment variables, and two setup modes.

### Configuration Commands

| Command                        | Description                                                         |
| ------------------------------ | ------------------------------------------------------------------- |
| `ax profiles create [name]`    | Create a new configuration profile interactively or from flags/file |
| `ax profiles update [name]`    | Update fields in an existing profile (uses active profile if omitted) |
| `ax profiles list`             | List all available profiles                                         |
| `ax profiles show [name]`      | Display a profile's configuration (uses active profile if omitted)  |
| `ax profiles use <profile>`    | Switch to a different profile                                       |
| `ax profiles validate [name]`  | Check a profile for missing or incorrect config (uses active if omitted) |
| `ax profiles delete <profile>` | Delete a configuration profile                                      |

### Configuration Modes

You can also create a profile non-interactively using CLI flags or a TOML file:

```bash
# Create with flags (no prompts)
ax profiles create staging --api-key ak_abc123 --region US --output-format json

# Create from a TOML file
ax profiles create production --from-file ./prod.toml

# Create from file and override the API key
ax profiles create production --from-file ./prod.toml --api-key ak_override
```

**Flag precedence (highest to lowest):** CLI flags → `--from-file` (TOML) → interactive prompts.

When you run `ax profiles create` without flags, you'll be prompted to choose between two configuration modes:

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
5. **Network**: Outbound proxy mode (system environment variables or a
   pinned HTTP CONNECT proxy URL), proxy bypass hosts, and CA bundle
6. **Output Format**: Default display format

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

[network]
# Precedence: ARIZE_PROXY_URL > https_proxy/HTTPS_PROXY >
# http_proxy/HTTP_PROXY > all_proxy/ALL_PROXY (lowercase wins).
proxy_mode = "system"
# Optional: use a profile-specific HTTP CONNECT proxy instead.
# proxy_mode = "url"
# proxy_url = "http://proxy.yourcompany.com:8080"
# no_proxy = "localhost,127.0.0.1,.yourcompany.internal"
# ca_bundle = "/etc/ssl/certs/corporate-ca.pem"

[storage]
directory = "~/.arize"
cache_enabled = true

[output]
format = "json"
```

### Configuration File Location

Configuration files are stored at:

| Profile        | Linux/macOS                        | Windows                                        |
| -------------- | ---------------------------------- | ---------------------------------------------- |
| `default`      | `~/.arize/config.toml`             | `%USERPROFILE%\.arize\config.toml`             |
| Named profiles | `~/.arize/profiles/<profile>.toml` | `%USERPROFILE%\.arize\profiles\<profile>.toml` |

### Updating a Profile

Use `ax profiles update` to modify specific fields in an existing profile without recreating it:

```bash
# Update the API key in the active profile
ax profiles update --api-key ak_new_key

# Update the region in a named profile
ax profiles update production --region EU

# Replace an entire profile from a TOML file
ax profiles update production --from-file ./prod.toml

# Load from file and override the API key
ax profiles update staging --from-file ./staging.toml --api-key ak_override
```

**Arguments:**

| Argument   | Description                                        |
| ---------- | -------------------------------------------------- |
| `[name]`   | Profile to update (uses active profile if omitted) |

**Options:**

| Option              | Description                                                 |
| ------------------- | ----------------------------------------------------------- |
| `--from-file`, `-f` | TOML file to load; completely replaces the existing profile |
| `--api-key`         | Arize API key                                               |
| `--region`          | Routing region (e.g. `us-east-1b`, `US`, `EU`)              |
| `--proxy-mode`      | Proxy source: `system` environment variables or `url`       |
| `--proxy-url`       | HTTP CONNECT proxy URL                                       |
| `--no-proxy`        | Comma-separated hosts that bypass the proxy                  |
| `--ca-bundle`       | CA bundle for a TLS-inspecting proxy or private endpoint     |
| `--output-format`   | Default output format (`table`, `json`, `csv`, `parquet`)   |
| `--verbose`, `-v`   | Enable verbose logs                                         |

With flags only, just the specified fields are updated; all others are preserved. With `--from-file`, the profile is fully replaced by the file contents (flags are still applied on top).

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

`request_verify` must be a boolean (or an environment-variable reference that
resolves to one). To trust a custom or corporate CA, use `network.ca_bundle`
instead of disabling verification.

**Network** (optional)

```toml
[network]
# Default: use standard process environment variables.
# Precedence: ARIZE_PROXY_URL > https_proxy/HTTPS_PROXY >
# http_proxy/HTTP_PROXY > all_proxy/ALL_PROXY (lowercase wins).
proxy_mode = "system"

# To pin a proxy to this profile, use `url` mode. This value may be an
# environment-variable reference so credentials are not stored in the profile.
# proxy_mode = "url"
# proxy_url = "${ARIZE_PROXY_URL}"
# no_proxy = "localhost,127.0.0.1,.internal.example.com"
# ca_bundle = "${ARIZE_SSL_CA_CERT}"
```

The proxy is applied to REST, OAuth, PyPI/GitHub downloads, Arrow Flight, and
OTLP/gRPC. The proxy must support HTTP CONNECT and HTTP/2 tunneling for Flight
and OTLP. Only `http://` proxy URLs are supported: in `system` mode,
environment values with other schemes (e.g. `socks5://`) are skipped with a
warning; in `url` mode they are rejected. `ca_bundle` is the preferred way to
trust a TLS-inspecting corporate proxy; do not disable certificate
verification unless troubleshooting a controlled environment. When no
supported proxy is configured, every AX transport connects directly; AX does
not defer to OS-level proxy discovery because it could select a proxy scheme
that Flight and OTLP cannot use.

`no_proxy` accepts a comma-separated list. Each entry may be a hostname
(`api.example.com`), a domain suffix (`.example.com`, which also matches the
bare domain), an IP or CIDR range (`10.0.0.0/8`), a bracketed IPv6 address,
or any of these with a port (`host:443`, matched against the URL's explicit
port or the scheme default). `*` may appear anywhere in the list and bypasses
the proxy for everything. `*.example.com` is accepted as a domain suffix.
Caveat: Arrow Flight and OTLP use gRPC's own bypass matching, which supports
hostnames, suffixes, and CIDR ranges but ignores port qualifiers.

While constructing gRPC transports, the CLI temporarily exports the resolved
settings as `grpc_proxy` and `no_grpc_proxy`, then restores the caller's
environment. In `system` mode a `grpc_proxy`/`no_grpc_proxy` you set yourself
is preserved; in `url` mode the profile's values take precedence. When
`ca_bundle` is set, it is also temporarily exported as
`GRPC_DEFAULT_SSL_ROOTS_FILE_PATH` and `OTEL_EXPORTER_OTLP_CERTIFICATE` so
Flight and trace export trust the same CA.

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

When you run `ax profiles create`, the CLI automatically detects existing `ARIZE_*` environment variables and offers to use them:

```bash
ax profiles create
```

```
Environment Variable Detection

  ✓ Detected ARIZE_API_KEY = ak_***************xyz
  ✓ Detected ARIZE_REGION = US

Create profiles from detected environment variables? [Y/n]: y
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
ax profiles show --expand
```

Without `--expand`, you'll see the variable references like `${ARIZE_API_KEY}`.

### Multiple Profiles

Create different profiles for different environments:

```bash
# Create a production profile (name as argument skips the name prompt)
ax profiles create production

# Create a staging profile interactively
ax profiles create staging

# List all profiles
ax profiles list

# Switch profiles
ax profiles use production
ax profiles use staging

# Update a field in a specific profile
ax profiles update staging --region EU

# Run commands against a different profile by switching first
ax profiles use production
ax datasets list

# Delete a profile (prompts for confirmation)
ax profiles delete staging

# Delete a profile without confirmation
ax profiles delete staging --force
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
ax <TAB>         # Shows available commands (cache, datasets, experiments, profiles, projects, spans, traces)
ax datasets <TAB> # Shows dataset subcommands (list, get, export, create, append, update, delete)
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

### Global Options

Available for all commands:

- `--output, -o <format>`: Set output format (`table`, `json`, `csv`, `parquet`, or a file path)
- `--help, -h`: Show help message

> **Note:** `--verbose, -v` is available on each individual subcommand (e.g., `ax datasets list --verbose`) rather than as a top-level flag.

> **Profiles:** Commands always use the active profile. Run `ax profiles use <name>` to switch profiles.

### AI Integrations

Configure external LLM providers for use within the Arize platform (for evaluations, online evals, and more):

```bash
# List AI integrations
ax ai-integrations list [--name <substring>] [--space <space>] [--limit 15] [--cursor <cursor>]

# Get a specific integration
ax ai-integrations get <integration>

# Create an integration (OpenAI example)
ax ai-integrations create --name "OpenAI Prod" --provider OPEN_AI \
  --api-key <key> --model-name gpt-4o --model-name gpt-4o-mini

# Create an integration with custom headers
ax ai-integrations create --name "Custom LLM" --provider CUSTOM \
  --base-url https://my-llm.example.com \
  --headers-json '{"X-API-Key": "secret"}'

# Create an AWS Bedrock integration
ax ai-integrations create --name "Bedrock" --provider AWS_BEDROCK \
  --provider-metadata-json '{"role_arn": "arn:aws:iam::123456789:role/MyRole"}'

# Update an integration
ax ai-integrations update <integration> --name "Renamed" --api-key <new-key>

# Delete an integration
ax ai-integrations delete <integration> [--force]
```

**Supported providers:**

| Provider      | Value         | Notes                                        |
| ------------- | ------------- | -------------------------------------------- |
| OpenAI        | `OPEN_AI`       |                                              |
| Azure OpenAI  | `AZURE_OPEN_AI` | Use `--base-url` for the deployment endpoint |
| AWS Bedrock   | `AWS_BEDROCK`   | Requires `--provider-metadata-json`          |
| Vertex AI     | `VERTEX_AI`     | Requires `--provider-metadata-json`          |
| Anthropic     | `ANTHROPIC`     |                                              |
| NVIDIA NIM    | `NVIDIA_NIM`    |                                              |
| Google Gemini | `GEMINI`        |                                              |
| Custom        | `CUSTOM`        | Use `--base-url` for a custom endpoint       |

### Annotation Configs

Manage annotation configs (rubrics for human and automated evaluation):

```bash
# List annotation configs
ax annotation-configs list [--name <substring>] [--space <space>] [--limit 15] [--cursor <cursor>]

# Get a specific annotation config
ax annotation-configs get <annotation-config>

# Create a freeform annotation config (free-text feedback)
ax annotation-configs create --name "Quality" --space <space> --type FREEFORM

# Create a continuous annotation config (numeric score range)
ax annotation-configs create --name "Score" --space <space> --type CONTINUOUS \
  --min-score 0 --max-score 1 --optimization-direction MAXIMIZE

# Create a categorical annotation config (discrete labels)
ax annotation-configs create --name "Verdict" --space <space> --type CATEGORICAL \
  --value good --value neutral --value bad --optimization-direction MAXIMIZE

# Delete an annotation config
ax annotation-configs delete <annotation-config> [--force]
```

**Supported annotation config types:**

| Type          | Required options                                                        | Optional options           |
| ------------- | ----------------------------------------------------------------------- | -------------------------- |
| `FREEFORM`    | _(none)_                                                                | —                          |
| `CONTINUOUS`  | `--min-score`, `--max-score`                                            | `--optimization-direction` |
| `CATEGORICAL` | `--value` (repeat for multiple labels, e.g. `--value good --value bad`) | `--optimization-direction` |

### Annotation Queues

Manage annotation queues for human review and labeling workflows:

```bash
# List annotation queues
ax annotation-queues list [--space <space>] [--name <substring>] [--limit 15] [--cursor <cursor>]

# Get a specific annotation queue
ax annotation-queues get <queue>

# Create an annotation queue (at least one --annotation-config-id required)
ax annotation-queues create --name "My Queue" --space <space> \
  --annotation-config-id <config-id>

# Create a queue with annotators and assignment method
ax annotation-queues create --name "My Queue" --space <space> \
  --annotation-config-id <config-id> \
  --annotator-email alice@example.com --annotator-email bob@example.com \
  --instructions "Please evaluate carefully" \
  --assignment-method RANDOM

# Create a queue and seed it with initial records from a file
ax annotation-queues create --name "My Queue" --space <space> \
  --annotation-config-id <config-id> \
  --record-sources sources.json

# Update a queue (list fields fully replace existing values)
ax annotation-queues update <queue> [--name <name>] [--instructions <text>] \
  [--annotation-config-id <id>] [--annotator-email <email>]

# Delete a queue
ax annotation-queues delete <queue> [--force]

# List records in a queue
ax annotation-queues list-records <queue> [--space <space>] [--limit 15] [--cursor <cursor>]

# Delete records from a queue
ax annotation-queues delete-records <queue> --record-id <id> [--record-id <id> ...] [--force]

# Annotate a record (upserted by annotation config name; call again for additional configs)
ax annotation-queues annotate-record <queue> <record-id> \
  --annotation-name "quality" [--score 0.9] [--label good] [--text "Looks great"]

# Assign users to a record (replaces all existing assignments)
ax annotation-queues assign-record <queue> <record-id> \
  --email alice@example.com [--email bob@example.com]

# Remove all assignments from a record
ax annotation-queues assign-record <queue> <record-id>

# Add records to a queue from a file
ax annotation-queues add-records <queue> \
  --space <space> \
  --record-sources sources.json

# Add records inline (span source)
ax annotation-queues add-records <queue> \
  --record-sources '[{"record_type": "SPAN", "project_id": "<proj>",
    "start_time": "2024-01-01T00:00:00Z", "end_time": "2024-01-02T00:00:00Z"}]'

# Add records inline (dataset example source)
ax annotation-queues add-records <queue> \
  --record-sources '[{"record_type": "EXAMPLE", "dataset_id": "<ds>",
    "example_ids": ["ex-1", "ex-2"]}]'
```

**Assignment methods:**

| Method       | Behavior                                      |
| ------------ | --------------------------------------------- |
| `ALL`        | Every annotator is assigned to every record (default) |
| `RANDOM`     | Each record is randomly assigned to one annotator |

### API Keys

> **Security note:** The raw key value is only returned once (on `create` and `refresh`). Store it securely immediately — it cannot be retrieved again.

```bash
# List API keys
ax api-keys list [--key-type USER|SERVICE] [--status ACTIVE|REVOKED] \
  [--limit 15] [--cursor <cursor>]

# Create a user key (authenticates as you)
ax api-keys create --name "My Key" [--description "..."] [--expires-at 2025-12-31T23:59:59]

# Create a service key (scoped to a space)
ax api-keys create --name "CI Key" --key-type SERVICE --space <space-name-or-id>

# Refresh a key (revokes old key, issues replacement)
ax api-keys refresh <key-id> [--expires-at 2025-12-31T23:59:59] \
  [--grace-period-seconds 300]

# Revoke a key
ax api-keys revoke <key-id> [--force]
```

**`refresh` options:**

| Option | Description |
| ------------------------- | --------------------------------------------------------------------------- |
| `--expires-at` | New expiration for the replacement key (ISO 8601). Omit for no expiration. |
| `--grace-period-seconds`  | Seconds the old key stays valid after refresh so clients can rotate. Omit (or pass `0`) to revoke the old key immediately. |

**Key types:**

| Type      | Description                                                              |
| --------- | ------------------------------------------------------------------------ |
| `user`    | Authenticates as the creating user. Global, so `--space` not needed.    |
| `service` | Scoped to a specific space. `--space` (name or ID) is required.         |

### Cache

Manage the local cache. The CLI caches downloaded resource data (e.g., dataset examples) locally as Parquet files to avoid redundant API calls. When you fetch a dataset's examples, the results are stored on disk so subsequent requests for the same version load instantly. The cache is automatically invalidated when a resource's `updated_at` timestamp changes, so you always get fresh data when something changes on the server.

Caching is enabled by default and can be toggled in your profile configuration:

```toml
[storage]
cache_enabled = true
```

```bash
# Clear the cache
ax cache clear
```

### Datasets

Manage your datasets:

```bash
# List datasets
ax datasets list [--name <substring>] [--space <space>] [--limit 15] [--cursor <cursor>]

# Get dataset metadata
ax datasets get <dataset>

# Export all examples to a file
ax datasets export <dataset> [--version-id <version-id>] [--output-dir .] [--stdout]

# Create a new dataset
ax datasets create --name "My Dataset" --space <space> --file data.csv

# Create a dataset from stdin (pipe or heredoc)
ax datasets create --name "My Dataset" --space <space> --file - < data.json

# Append examples (inline JSON)
ax datasets append <dataset> --json '[{"question": "...", "answer": "..."}]'

# Append examples (from file)
ax datasets append <dataset> --file new_examples.csv [--version-id <version-id>]

# Append examples from stdin
ax datasets append <dataset> --file -

# Update a dataset (e.g. rename)
ax datasets update <dataset> --new-name "New Name" [--space <space>]

# Delete a dataset
ax datasets delete <dataset> [--force]
```

**Supported data file formats:**

- CSV (`.csv`)
- JSON (`.json`)
- JSON Lines (`.jsonl`)
- Parquet (`.parquet`)
- stdin (`-` or `/dev/stdin`) — format auto-detected from content

### Evaluators

Manage LLM-as-judge evaluators and their versions:

```bash
# List evaluators (optionally filtered by space)
ax evaluators list [--name <substring>] [--space <space>] [--limit 15] [--cursor <cursor>]

# Get an evaluator with its latest version
ax evaluators get <evaluator>

# Get an evaluator at a specific version
ax evaluators get <evaluator> --version-id <version-id>

# Create a new template evaluator
ax evaluators create-template-evaluator \
  --name "Response Relevance" \
  --space <space> \
  --commit-message "Initial version" \
  --template-name relevance \
  --template "Is this response relevant to the query? {{input}} {{output}}" \
  --ai-integration-id <integration-id> \
  --model-name gpt-4o

# Create a classification evaluator (label → numeric score; omit flag for freeform)
ax evaluators create-template-evaluator \
  --name "Relevance classifier" \
  --space <space> \
  --commit-message "Initial version" \
  --template-name relevance \
  --template "Classify: {{output}}" \
  --ai-integration-id <integration-id> \
  --model-name gpt-4o \
  --classification-choices '{"relevant":1,"irrelevant":0}' \
  --direction maximize \
  --data-granularity SPAN

# Update evaluator metadata
ax evaluators update <evaluator> --name "New Name"
ax evaluators update <evaluator> --description "Updated description"

# Delete an evaluator (and all its versions)
ax evaluators delete <evaluator> [--force]

# List all versions of an evaluator
ax evaluators list-versions <evaluator-id> [--limit 15] [--cursor <cursor>]

# Get a specific version by ID
ax evaluators get-version <version-id>

# Create a new template version of an existing evaluator
ax evaluators create-template-evaluator-version <evaluator-id> \
  --commit-message "Improved prompt" \
  --template-name relevance \
  --template "Rate the relevance of the response: {{input}} {{output}}" \
  --ai-integration-id <integration-id> \
  --model-name gpt-4o

# Same optional template fields apply (e.g. classification choices)
ax evaluators create-template-evaluator-version <evaluator-id> \
  --commit-message "Add rails" \
  --template-name relevance \
  --template "Classify: {{output}}" \
  --ai-integration-id <integration-id> \
  --model-name gpt-4o \
  --classification-choices '{"relevant":1,"irrelevant":0}'
```

**Template configuration options:**

| Option | Description |
| --- | --- |
| `--template-name` | Eval column name (alphanumeric, spaces, hyphens, underscores) |
| `--template` | Prompt template with `{{variable}}` placeholders referencing span attributes |
| `--ai-integration-id` | AI integration global ID (base64) |
| `--model-name` | Model name (e.g. `gpt-4o`, `claude-3-5-sonnet`) |
| `--include-explanations` | Include reasoning explanation alongside the score (default: on) |
| `--use-function-calling` | Prefer structured function-call output when supported (default: on) |
| `--invocation-params` | JSON object of model invocation parameters (e.g. `'{"temperature": 0.7}'`) |
| `--provider-params` | JSON object of provider-specific parameters |
| `--classification-choices` | JSON object mapping labels to numeric scores (e.g. `'{"relevant":1,"irrelevant":0}'`); omit for freeform output |
| `--direction` | `maximize` or `minimize` (optimization direction for scores) |
| `--data-granularity` | `span`, `trace`, or `session` |

#### Code evaluators

`create-code-evaluator` and `create-code-evaluator-version` accept `--code-type managed` for
built-in checks (regex, JSON parse, keyword matches, exact match) or
`--code-type custom` for user-supplied Python.

```bash
# Managed built-in: regex check
ax evaluators create-code-evaluator \
  --name "Regex Check" \
  --space <space> \
  --commit-message "Initial version" \
  --code-type managed \
  --code-name regex_match \
  --managed-evaluator MATCHES_REGEX \
  --variables '["output"]' \
  --static-params '[{"name":"pattern","type":"REGEX","default_value":"^yes"}]'

# Custom Python, loading source from a file (use @ prefix)
ax evaluators create-code-evaluator \
  --name "Custom Eval" \
  --space <space> \
  --commit-message "Initial version" \
  --code-type custom \
  --code-name my_eval \
  --code @./evaluator.py \
  --imports @./imports.py \
  --variables '["input","output"]'

# Inline custom code is also supported in create-code-evaluator-version
ax evaluators create-code-evaluator-version <evaluator-id> \
  --commit-message "v2" \
  --code-type custom \
  --code-name my_eval \
  --code 'class MyEval:
      def evaluate(self, output):
          return 1 if "yes" in output else 0' \
  --variables '["output"]'
```

**Code configuration options:**

| Option | Description |
| --- | --- |
| `--code-type` | `managed` (built-in) or `custom` (user Python) |
| `--code-name` | Eval column name |
| `--managed-evaluator` | Built-in evaluator (`--code-type managed`): `MATCHES_REGEX`, `JSON_PARSEABLE`, `CONTAINS_ANY_KEYWORD`, `CONTAINS_ALL_KEYWORDS`, `EXACT_MATCH` |
| `--code` | Python source for `--code-type custom`. Inline source, or `@path/to/file.py` to load from disk |
| `--imports` | Optional Python import block for `--code-type custom`. Inline or `@path/to/file.py` |
| `--variables` | JSON array of variable names (span attributes / columns). Accepts inline JSON or a file path |
| `--static-params` | JSON array of static parameters. Each item: `{name, type: STRING\|STRING_ARRAY\|REGEX, default_value: <string or array of strings>}` |
| `--query-filter` | Optional filter query applied to the chosen granularity |
| `--data-granularity` | `span`, `trace`, or `session` |

### Experiments

Run and analyze experiments on your datasets:

```bash
# List experiments (optionally filtered by dataset)
ax experiments list [--dataset <dataset>] [--limit 15] [--cursor <cursor>]

# Get a specific experiment
ax experiments get <experiment>

# Export all runs from an experiment
ax experiments export <experiment> [--output-dir .] [--stdout]

# Run an experiment — execute a task function against a dataset and upload results
ax experiments run --dataset <dataset> --name "My Experiment" --task task.py

# Dry-run to validate locally without uploading (processes first 10 examples)
ax experiments run --dataset <dataset> --name "My Experiment" --task task.py --dry-run

# Create a new experiment from a pre-computed data file
ax experiments create --name "My Experiment" --dataset <dataset> --file runs.csv

# Create an experiment from stdin
ax experiments create --name "My Experiment" --dataset <dataset> --file -

# List runs for an experiment (paginated)
ax experiments list-runs <experiment> [--limit 30] [--cursor <cursor>]

# Delete an experiment
ax experiments delete <experiment> [--force]
```

#### `ax experiments run` — execute a task locally

`ax experiments run` downloads the dataset examples, runs your task function against each one
with configurable concurrency, and uploads the results as a new experiment.

**Task file format**

Create a Python file that defines a top-level `task` function. It receives a dataset
[`Example`](https://arize-client-python.readthedocs.io) and must return a JSON-serialisable value:

```python
# task.py
def task(dataset_row) -> str:
    question = dataset_row["question"]
    return my_llm_call(question)  # call your model or application here
```

The function runs once per dataset example. Any JSON-serialisable return type is accepted
(`str`, `dict`, `list`, `int`, `float`, `bool`, `None`).

**`run` options:**

| Option | Description |
| --- | --- |
| `--dataset` | Dataset name or ID to run against _(required)_ |
| `--name`, `-n` | Experiment name _(required)_ |
| `--task` | Path to the Python task file _(required)_ |
| `--space`, `-s` | Space name or ID (required if using dataset name instead of ID) |
| `--concurrency`, `-c` | Number of concurrent task executions (default: 3) |
| `--dry-run` | Run locally on the first 10 examples without uploading results |
| `--verbose`, `-v` | Enable verbose logs |

> **Note:** The data file for `experiments create` must contain `example_id` and `output` columns. Extra columns are passed through as additional fields.

**Export options:**

| Option            | Description                                    |
| ----------------- | ---------------------------------------------- |
| `--output-dir`    | Output directory (default: current directory)  |
| `--stdout`        | Print JSON to stdout instead of saving to file |
| `--verbose`, `-v` | Enable verbose logs                            |

### Organizations

Manage organizations:

```bash
# List organizations
ax organizations list [--name <substring>] [--limit 50] [--cursor <cursor>]

# Get an organization by name or ID
ax organizations get <organization>

# Create a new organization
ax organizations create --name "My Org" [--description "..."]

# Update an organization's name or description (at least one field required)
ax organizations update <organization> --name "New Name"
ax organizations update <organization> --description "Updated description"

# Add a user to an organization (or update their role if already a member)
ax organizations add-user <organization> --user-id <user-id> --role <role>

# Remove a user from an organization (also removes them from all child spaces)
ax organizations remove-user <organization> --user-id <user-id> [--force]

# Delete an organization (irreversible)
ax organizations delete <organization> [--force]
```

**Organization roles:** `admin`, `member`, `read-only`, `annotator`

### Projects

Organize your projects:

```bash
# List projects
ax projects list [--name <substring>] [--space <space>] [--limit 15] [--cursor <cursor>]

# Get project metadata
ax projects get <project>

# Create a new project
ax projects create --name "My Project" --space <space>

# Update a project (by ID or name)
ax projects update <project> --name "Updated Name" [--space <space>]

# Delete a project
ax projects delete <project> [--force]
```

### Prompts

Manage versioned prompt templates with label-based deployment:

```bash
# List prompts
ax prompts list [--name <substring>] [--space <space>] [--limit 15] [--cursor <cursor>]

# Get a prompt (latest version by default)
ax prompts get <prompt>

# Get a specific version by ID or label
ax prompts get <prompt> --version-id <version-id>
ax prompts get <prompt> --label production

# Create a prompt with an initial version
ax prompts create \
  --name "My Prompt" \
  --space <space> \
  --provider OPEN_AI \
  --input-variable-format F_STRING \
  --messages messages.json \
  --commit-message "Initial version"

# Create a prompt with invocation and provider parameters
ax prompts create \
  --name "My Prompt" \
  --space <space> \
  --provider OPEN_AI \
  --model gpt-4o \
  --input-variable-format F_STRING \
  --messages messages.json \
  --commit-message "Initial version" \
  --invocation-params '{"temperature": 0.7, "max_tokens": 512}' \
  --provider-params '{"deployment": "my-deployment"}'

# Update a prompt's description
ax prompts update <prompt> --description "Updated description"

# Delete a prompt (removes all versions)
ax prompts delete <prompt> [--force]

# List versions for a prompt
ax prompts list-versions <prompt> [--limit 15] [--cursor <cursor>]

# Create a new version
ax prompts create-version <prompt> \
  --provider OPEN_AI \
  --input-variable-format F_STRING \
  --messages messages_v2.json \
  --commit-message "Improved system prompt"

# Create a new version (inline messages JSON)
ax prompts create-version <prompt> \
  --provider OPEN_AI \
  --input-variable-format F_STRING \
  --messages '[{"role": "USER", "content": "Your prompt here"}]' \
  --commit-message "Minimal inline JSON example"

# Create a new version with invocation and provider parameters
ax prompts create-version <prompt> \
  --provider OPEN_AI \
  --model gpt-4o \
  --input-variable-format F_STRING \
  --messages messages_v2.json \
  --commit-message "Tuned parameters" \
  --invocation-params '{"temperature": 0.5}' \
  --provider-params '{"deployment": "my-deployment"}'


# Resolve a label to its version
ax prompts get-version-by-label <prompt> --label production

# Set labels on a version (replaces all existing labels)
ax prompts set-version-labels <version-id> --label production --label staging

# Remove a label from a version
ax prompts remove-version-label <version-id> --label staging
```

**Messages** (`--messages`): pass a path to a JSON file, or inline JSON. Inline values must start with `[` or `{` after whitespace (so a missing file path like `msgs.json` yields a clear “file not found” error instead of a JSON parse error). The payload must be a non-empty JSON array of message objects. Example file `messages.json`:

```json
[
  {"role": "SYSTEM", "content": "You are a helpful assistant."},
  {"role": "USER",   "content": "Summarize the following: {text}"},
  {"role": "ASSISTANT", "tool_calls": [{"id": "tool-call-1", "type": "FUNCTION", "function": {"name": "search", "arguments": "{\"query\": \"summarize {text}\"}}]},
  {"role": "TOOL", "tool_call_id": "tool-call-1", "content": "This is the result of the search function."},
]
```

**`create` / `create-version` options:**

| Option | Description |
| --- | --- |
| `--invocation-params` | JSON object (or `@file.json`) of model invocation parameters (e.g. `temperature`, `max_tokens`, `top_p`) |
| `--provider-params` | JSON object (or `@file.json`) of provider-specific parameters (e.g. Azure deployment name, Bedrock region) |

**Input variable formats:**

| Format     | Syntax              |
| ---------- | ------------------- |
| `F_STRING` | `{variable_name}`   |
| `MUSTACHE` | `{{variable_name}}` |
| `NONE`     | No variable parsing |

### Roles

Manage custom roles with granular permissions:

```bash
# List all roles (predefined and custom)
ax roles list [--limit 15] [--cursor <cursor>]

# List only custom roles
ax roles list --is-custom

# List only system-defined predefined roles
ax roles list --is-predefined

# Get a role by name or ID
ax roles get <role-name-or-id>

# Create a custom role (at least one permission required)
ax roles create --name "Data Analyst" --permissions DATASET_READ,PROJECT_READ

# Create with description
ax roles create --name "Data Analyst" --permissions DATASET_READ --description "Read-only data access"

# Update a role (at least one field required; --permissions fully replaces existing permissions)
ax roles update <role-name-or-id> --name "Senior Analyst"
ax roles update <role-name-or-id> --permissions DATASET_READ,DATASET_CREATE

# Delete a role by name or ID (pass --force to skip confirmation)
ax roles delete <role-name-or-id> [--force]
```

> **Note:** Permission values are uppercase identifiers such as `PROJECT_READ`, `DATASET_CREATE`, `ANNOTATION_CONFIG_READ`, etc. Predefined (system-managed) roles cannot be created, updated, or deleted.

### Spaces

Manage spaces:

```bash
# List spaces
ax spaces list [--organization-id <org-id>] [--limit 15] [--cursor <cursor>]

# Get a space by name or ID
ax spaces get <space>

# Create a new space
ax spaces create --name "My Space" --organization-id <org-id> [--description "..."]

# Update a space's name or description (at least one field required)
ax spaces update <space> --name "New Name"
ax spaces update <space> --description "Updated description"

# Delete a space and all resources within it
ax spaces delete <space> [--force]

# Add a user to a space (or update their role if already a member)
# The user must already be a member of the space's parent organization.
ax spaces add-user <space> --user-id <user-id> --role <role>

# Remove a user from a space
ax spaces remove-user <space> --user-id <user-id> [--force]
```

**Space roles:** `admin`, `member`, `read-only`, `annotator`

> **Warning:** `ax spaces delete` permanently deletes the space and all of its contents, including all models, monitors, dashboards, datasets, custom metrics, and experiments.

### Skills

Install Arize context skills for AI coding agents. Skills are Markdown files that teach agents (Claude Code, Cursor, Codex, Windsurf) about the Arize API, tracing patterns, and CLI usage so they can answer questions and generate correct code without needing to look things up.

```bash
# Interactive install (detects installed agents, prompts for selection)
ax skills install

# Install for a specific agent, non-interactively
ax skills install --agent claude-code --yes

# Install for multiple agents
ax skills install --agent claude-code --agent cursor --yes

# Install globally (~/.claude/skills/, ~/.cursor/skills/, ~/.codex/skills/, ~/.windsurf/skills/)
ax skills install --global

# Overwrite existing skills
ax skills install --agent claude-code --force --yes

# Remove installed skills (checks all known agents)
ax skills clear
ax skills clear --yes

# Remove for a specific agent only
ax skills clear --agent claude-code
```

**Install locations:**

Skills are installed relative to the current working directory by default, or to `~` when `--global` is used:

| Agent | Project install | Global install |
|---|---|---|
| Claude Code | `./.claude/skills/` | `~/.claude/skills/` |
| Cursor | `./.cursor/skills/` | `~/.cursor/skills/` |
| Codex | `./.codex/skills/` | `~/.codex/skills/` |
| Windsurf | `./.windsurf/skills/` | `~/.windsurf/skills/` |

**Options:**

| Option | Description |
|---|---|
| `--agent`, `-a` | Agent to install for (repeatable). Values: `claude-code`, `cursor`, `codex`, `windsurf` |
| `--global`, `-g` | Install to home directory instead of current project |
| `--project-dir`, `-d` | Project directory (default: cwd) |
| `--yes`, `-y` | Skip confirmations. Requires `--agent`. Without `--force`, skips existing skills instead of overwriting |
| `--force`, `-f` | Overwrite existing skills without prompting |

### Spans

Export LLM spans from a project. Spans are individual units of work (e.g., an LLM call, a tool call) within a trace. By default spans are written to a JSON file; use `--stdout` to print to stdout instead.

```bash
# Export all spans (writes to file by default)
ax spans export <project-id>

# Export with filter
ax spans export <project-id> --filter "status_code = 'ERROR'"

# Export by trace, span, or session ID
ax spans export <project-id> --trace-id <trace-id>
ax spans export <project-id> --span-id <span-id>
ax spans export <project-id> --session-id <session-id>

# Export to stdout
ax spans export <project-id> --stdout
```

**Options:**

| Option            | Description                                                           |
| ----------------- | --------------------------------------------------------------------- |
| `--trace-id`      | Filter by trace ID                                                    |
| `--span-id`       | Filter by span ID                                                     |
| `--session-id`    | Filter by session ID                                                  |
| `--filter`        | Filter expression (e.g. `status_code = 'ERROR'`, `latency_ms > 1000`) |
| `--space`      | Space ID (required when using `--all` for Arrow Flight export)        |
| `--limit`, `-n`   | Maximum number of spans to export (default: 100)                      |
| `--days`          | Lookback window in days (default: 30)                                 |
| `--start-time`    | Override start of time window (ISO 8601)                              |
| `--end-time`      | Override end of time window (ISO 8601)                                |
| `--output-dir`    | Output directory (default: current directory)                         |
| `--stdout`        | Print JSON to stdout instead of saving to file                        |
| `--verbose`, `-v` | Enable verbose logs                                                   |

**Examples:**

```bash
ax spans export <project-id> --filter "status_code = 'ERROR'"
ax spans export <project-id> --filter "latency_ms > 1000"
ax spans export <project-id> --trace-id abc123 --filter "latency_ms > 1000"
ax spans export <project-id> --start-time 2024-01-01T00:00:00Z --end-time 2024-01-02T00:00:00Z
```

**Deleting spans:**

```bash
# Delete one or more spans by ID (prompts for confirmation)
ax spans delete <project-id> --span-id <span-id> [--span-id <span-id> ...] [--space <space>]

# Delete without confirmation
ax spans delete <project-id> --span-id <span-id> --force

# Comma-separated IDs are also accepted
ax spans delete <project-id> --span-id id1,id2,id3 --force
```

> **Note:** `ax spans delete` is irreversible. Spans not found within the supported lookback window are silently ignored (exit code 0). Partial failures are reported but do not change the exit code.

### Tasks

Manage evaluation tasks and run-experiment tasks, and trigger on-demand runs:

```bash
# List tasks (filtered by space, project, dataset, or type)
ax tasks list [--name <substring>] [--space <space>] [--project-id <project-name-or-id>] \
  [--dataset-id <dataset-id>] \
  [--task-type TEMPLATE_EVALUATION|CODE_EVALUATION|RUN_EXPERIMENT] \
  [--limit 15] [--cursor <cursor>]

# Get a specific task
ax tasks get <task-id>

# ── Evaluation tasks (TEMPLATE_EVALUATION / CODE_EVALUATION) ─────────────────

# Create a project-based evaluation task (use ax evaluators list to find IDs)
ax tasks create \
  --name "Relevance Check" \
  --task-type TEMPLATE_EVALUATION \
  --evaluators '[{"evaluator_id": "<id from ax evaluators list>", "query_filter": null, "column_mappings": null}]' \
  --project <project> [--space <space>] \
  --is-continuous

# Create a dataset-based evaluation task
ax tasks create \
  --name "Dataset Eval" \
  --task-type TEMPLATE_EVALUATION \
  --evaluators '[{"evaluator_id": "<evaluator-id>"}]' \
  --dataset <dataset> \
  --experiment-ids <exp-id-1>,<exp-id-2>

# Narrower subcommand (same options, cleaner help text)
ax tasks create-evaluation \
  --name "Relevance Check" \
  --task-type TEMPLATE_EVALUATION \
  --evaluators '[{"evaluator_id": "<id>"}]' \
  --project <project>

# ── Run-experiment tasks ──────────────────────────────────────────────────────

# Create a run-experiment task (dispatched via ax tasks create)
ax tasks create \
  --name "LLM Eval Run" \
  --task-type RUN_EXPERIMENT \
  --dataset <dataset> \
  --run-configuration '{
    "experiment_type": "LLM_GENERATION",
    "ai_integration_id": "<integration-id>",
    "model_name": "gpt-4o",
    "input_variable_format": "MUSTACHE",
    "messages": [{"role": "USER", "content": "{{input}}"}]
  }'

# Or use the dedicated subcommand
ax tasks create-run-experiment \
  --name "LLM Eval Run" \
  --dataset <dataset> \
  --run-configuration @run_config.json [--space <space>]

# ── Common task management ────────────────────────────────────────────────────

# Update mutable fields on an evaluation task (provide at least one field)
ax tasks update <task> --name "New Name"
ax tasks update <task> --sampling-rate 0.25
ax tasks update <task> --is-continuous
ax tasks update <task> --query-filter "attributes.env = 'prod'"
ax tasks update <task> --query-filter ""    # clear the task-level query filter
ax tasks update <task> --evaluators '[{"evaluator_id": "<id>"}]'

# Update the run configuration on a run_experiment task
ax tasks update <task> --run-configuration @new_config.json

# Delete a task (irreversible; prompts unless --force is passed)
ax tasks delete <task> [--space <space>] [--force]

# ── Triggering runs ───────────────────────────────────────────────────────────

# Trigger an on-demand evaluation run
ax tasks trigger-run <task-id>

# Trigger a run and wait for it to complete
ax tasks trigger-run <task-id> --wait

# Trigger an evaluation run over a specific data window
ax tasks trigger-run <task-id> \
  --data-start-time 2024-01-01T00:00:00Z \
  --data-end-time 2024-01-02T00:00:00Z \
  --max-spans 5000

# Trigger a run-experiment run (SDK dispatches based on task type)
ax tasks trigger-run <task-id> \
  --experiment-name "My Experiment" \
  --dataset-version-id <version-id> \
  --max-examples 200 \
  --tracing-metadata '{"env": "prod"}'

# Run against specific example IDs instead of all/N examples
ax tasks trigger-run <task-id> \
  --experiment-name "My Experiment" \
  --example-ids <example-id-1>,<example-id-2>

# Chain evaluation tasks to run after the experiment completes
ax tasks trigger-run <task-id> \
  --experiment-name "My Experiment" \
  --evaluation-task-ids <eval-task-id-1>,<eval-task-id-2>

# ── Run management ────────────────────────────────────────────────────────────

# List runs for a task (optionally filtered by status)
ax tasks list-runs <task-id> [--status PENDING|RUNNING|COMPLETED|FAILED|CANCELLED] \
  [--limit 15] [--cursor <cursor>]

# Get a specific run
ax tasks get-run <run-id>

# Cancel a run (only valid when pending or running)
ax tasks cancel-run <run-id> [--force]

# Wait for a run to reach a terminal state
ax tasks wait-for-run <run-id> [--poll-interval 5] [--timeout 600]
```

**`create` / `create-evaluation` options:**

| Option | Description |
| --- | --- |
| `--name`, `-n` | Task name (must be unique within the space) |
| `--task-type` | `template_evaluation`, `code_evaluation`, or `run_experiment` |
| `--evaluators` | JSON array of evaluator configs (evaluation tasks only). Get IDs via `ax evaluators list`. Example: `[{"evaluator_id": "<id>", "query_filter": null, "column_mappings": null}]` |
| `--run-configuration` | JSON object or `@file.json` with the run configuration (`run_experiment` tasks only) |
| `--project` | Project name or ID; mutually exclusive with `--dataset` (evaluation tasks only) |
| `--space` | Space name or ID (helps resolve project/dataset names) |
| `--dataset` | Dataset name or ID; required for `run_experiment` tasks, mutually exclusive with `--project` for evaluation tasks |
| `--experiment-ids` | Comma-separated experiment IDs (evaluation tasks, dataset-based only) |
| `--sampling-rate` | Fraction of data to evaluate (0–1); project evaluation tasks only |
| `--is-continuous` / `--no-continuous` | Run continuously on incoming data (evaluation tasks only) |
| `--query-filter` | Task-level filter applied to all evaluators (evaluation tasks only) |

**`create-run-experiment` options:**

| Option | Description |
| --- | --- |
| `--name`, `-n` | Task name (must be unique within the space) |
| `--dataset` | Dataset name or ID to run experiments against |
| `--run-configuration` | JSON object or `@file.json` with the run configuration |
| `--space`, `-s` | Space name or ID |

**`update` options:** (must provide at least one field)

| Option | Description |
| --- | --- |
| `--name`, `-n` | New task display name |
| `--sampling-rate` | Sampling rate between 0 and 1 (evaluation tasks only) |
| `--is-continuous` / `--no-continuous` | Whether the task runs continuously (evaluation tasks only) |
| `--query-filter` | Task-level query filter; pass `""` to clear (evaluation tasks only) |
| `--evaluators` | JSON array replacing the full evaluator list (evaluation tasks only) |
| `--run-configuration` | JSON object or `@file.json` replacing the run configuration (`run_experiment` tasks only) |
| `--space`, `-s` | Space name or ID (helps resolve task by name) |

**`delete` options:**

| Option | Description |
| --- | --- |
| `--space`, `-s` | Space name or ID (helps resolve task by name) |
| `--force`, `-f` | Skip the interactive confirmation prompt |

**`trigger-run` options:**

| Option | Description |
| --- | --- |
| `--data-start-time` | ISO 8601 start of the data window (evaluation tasks only) |
| `--data-end-time` | ISO 8601 end of the data window (defaults to now; evaluation tasks only) |
| `--max-spans` | Maximum spans to evaluate (default: 10 000; evaluation tasks only) |
| `--override-evaluations` | Re-evaluate data that already has labels (evaluation tasks only) |
| `--experiment-ids` | Comma-separated experiment IDs; dataset-based evaluation tasks only |
| `--experiment-name` | Display name for the experiment to be created (`run_experiment` tasks only) |
| `--dataset-version-id` | Dataset version ID; defaults to latest (`run_experiment` tasks only) |
| `--max-examples` | Maximum examples to run (`run_experiment` tasks only). Mutually exclusive with `--example-ids` |
| `--example-ids` | Comma-separated example IDs to run against (`run_experiment` tasks only). Mutually exclusive with `--max-examples` |
| `--tracing-metadata` | JSON object or `@file.json` of key/value pairs for experiment traces (`run_experiment` tasks only) |
| `--evaluation-task-ids` | Comma-separated evaluation task IDs to trigger after the run completes (`run_experiment` tasks only) |
| `--wait`, `-w` | Block until the run reaches a terminal state |
| `--poll-interval` | Seconds between polling attempts when `--wait` is set (default: 5) |
| `--timeout` | Maximum seconds to wait when `--wait` is set (default: 600) |

### Traces

Query traces in a project. A trace is a collection of spans representing a full request or conversation; the CLI identifies traces by their root span (`parent_id = null`). The CLI automatically applies `parent_id = null`; any `--filter` you provide is ANDed with it.

```bash
# List traces
ax traces list <project-id> [--start-time <iso8601>] [--end-time <iso8601>] \
  [--filter "<expr>"] [--limit 15] [--cursor <cursor>] [--output <format>]
```

**Options:**

| Option            | Description                                                             |
| ----------------- | ----------------------------------------------------------------------- |
| `--start-time`    | Start of time window, inclusive (ISO 8601, e.g. `2024-01-01T00:00:00Z`) |
| `--end-time`      | End of time window, exclusive (ISO 8601). Defaults to now               |
| `--filter`        | Filter expression (e.g. `status_code = 'ERROR'`, `latency_ms > 1000`)   |
| `--limit`, `-n`   | Maximum number of traces to return (default: 15)                        |
| `--cursor`        | Pagination cursor for the next page                                     |
| `--output`, `-o`  | Output format (`table`, `json`, `csv`, `parquet`) or file path          |
| `--verbose`, `-v` | Enable verbose logs                                                     |

**Filter examples:**

```bash
ax traces list <project-id> --filter "status_code = 'ERROR'"
ax traces list <project-id> --start-time 2024-01-01T00:00:00Z
ax traces list <project-id> --filter "latency_ms > 5000" --limit 50
```

### Users

Manage users in the account:

```bash
# List users (optionally filtered by email or status)
ax users list [--email <substring>] [--status ACTIVE] [--status INVITED] \
  [--limit 50] [--cursor <cursor>]

# Get a specific user by ID
ax users get <user-id>

# Create a new user and invite them
ax users create --full-name "Jane Doe" --email jane@example.com \
  --role MEMBER --invite-mode EMAIL_LINK

# Update a user's full name or developer permission flag
ax users update <user-id> --full-name "Jane Smith"
ax users update <user-id> --is-developer
ax users update <user-id> --no-is-developer

# Delete one or more users by ID (comma-separated or repeated flag)
ax users delete --id <user-id> [--force]
ax users delete --id id1,id2,id3 [--force]

# Delete by email address (resolves to user ID before deletion)
ax users delete --email user@example.com [--force]

# Mix IDs and emails; each deletion is attempted independently
ax users delete --id id1 --email user@example.com [--force]

# Resend an invitation email to a pending user
ax users resend-invitation <user-id>

# Send a password-reset email to a user
ax users reset-password <user-id>
```

**Account-level roles:** `admin`, `member`, `annotator`

**Invite modes:**

| Mode                 | Description                                          |
| -------------------- | ---------------------------------------------------- |
| `none`               | Create the user without sending any invitation       |
| `email_link`         | Send an invitation email with a sign-in link         |
| `temporary_password` | Send an email with a one-time temporary password     |

> **Note:** `ax users delete` accepts `--id` and/or `--email` flags (both accept comma-separated values or repeated flags). Emails are resolved to user IDs before deletion. Each deletion is attempted independently; the results table reports the outcome (`deleted`, `failed`, `not_found`) per user. Deletion cascades to all organization memberships, space memberships, API keys, and role bindings.

## Usage Examples

### Creating a Dataset from a CSV File

```bash
ax datasets create \
  --name "Customer Churn Dataset" \
  --space sp_abc123 \
  --file ./data/churn.csv
```

### Creating a Dataset from stdin

Use `-` (or `/dev/stdin`) as the file path to pipe data directly into the CLI. Format is auto-detected from the content (JSON array, JSONL, or CSV).

```bash
# Pipe from a file
cat data.json | ax datasets create \
  --name "customer-support-evals" \
  --space "U3BhY2U6OTA1MDoxSmtS" \
  --file -

# Inline heredoc — useful for scripting or quick one-offs
ax datasets create \
  --name "customer-support-evals" \
  --space "U3BhY2U6OTA1MDoxSmtS" \
  --file - <<'EOF'
[
  {"question": "How do I reset my password?", "ideal_answer": "Go to the login page and click 'Forgot Password'. Enter your email address and we'll send you a reset link within a few minutes.", "category": "Account Management"},
  ...
]
EOF
```

### Exporting Dataset List to JSON

```bash
ax datasets list --space sp_abc123 --output json > datasets.json
```

### Exporting Dataset Examples

```bash
# Export to a timestamped directory
ax datasets export ds_xyz789

# Export a specific version
ax datasets export ds_xyz789 --version-id ver_abc123

# Pipe to jq for processing
ax datasets export ds_xyz789 --stdout | jq '.[].input'
```

### Running an Experiment with a Task

Create a task file that calls your LLM or application:

```python
# task.py
import os
import openai

client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

def task(dataset_row) -> str:
    question = dataset_row["question"]
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": question}],
    )
    return response.choices[0].message.content
```

Then run the experiment:

```bash
# Validate locally first (first 10 examples, no upload)
ax experiments run \
  --dataset ds_abc123 \
  --name "GPT-4o-mini eval" \
  --task task.py \
  --dry-run

# Run against the full dataset and upload results
ax experiments run \
  --dataset ds_abc123 \
  --name "GPT-4o-mini eval" \
  --task task.py \
  --concurrency 5
```

### Exporting Experiment Runs

```bash
# Export all runs to a timestamped directory
ax experiments export exp_abc123

# Pipe to stdout for processing
ax experiments export exp_abc123 --stdout | jq '.[] | select(.output != null)'
```

### Exporting Spans by Trace ID

```bash
# Export all spans in a trace
ax spans export proj_abc123 --trace-id tr_xyz789

# Export a session's spans to stdout
ax spans export proj_abc123 --session-id sess_456 --stdout

# Export with a custom lookback window
ax spans export proj_abc123 --trace-id tr_xyz789 --days 7
```

### Exporting Spans

```bash
# Export all spans from a project
ax spans export proj_abc123

# Export error spans
ax spans export proj_abc123 --filter "status_code = 'ERROR'" --limit 100

# Export spans in a time window to stdout
ax spans export proj_abc123 --start-time 2024-01-01T00:00:00Z --end-time 2024-01-02T00:00:00Z --stdout
```

### Listing Traces and Exporting to Parquet

```bash
# List root traces in a project
ax traces list proj_abc123

# Export slow traces to Parquet for analysis
ax traces list proj_abc123 --filter "latency_ms > 2000" --limit 500 --output traces_slow.parquet

# List traces in JSON format
ax traces list proj_abc123 --output json
```

### Pagination

List more datasets using pagination:

```bash
# First page
ax datasets list --space sp_abc123 --limit 20

# Next page (use cursor from previous response)
ax datasets list --space sp_abc123 --limit 20 --cursor <cursor-value>
```

### Working with Multiple Environments

```bash
# Setup profiles for different environments
ax profiles create  # Create "production" profile
ax profiles create  # Create "staging" profile

# Switch contexts
ax profiles use production
ax datasets list --space sp_prod123

ax profiles use staging
ax datasets list --space sp_stage456
```

### Filtering Spans by Status

```bash
ax spans export <project-id> --filter "status_code = 'ERROR'" --stdout
```

### Listing Traces in a Time Window

```bash
ax traces list <project-id> \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-02T00:00:00Z
```

## Advanced Topics

### Output Formats

The CLI supports multiple output formats:

1. **Table** (default): Human-readable table format
2. **JSON**: Machine-readable JSON
3. **CSV**: Comma-separated values
4. **Parquet**: Apache Parquet columnar format

Set default format in profiles:

```bash
ax profiles create  # Select output format during setup
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
DATASETS=$(ax datasets list --space sp_abc123 --output json)

# Process with jq
echo "$DATASETS" | jq '.data[] | select(.name | contains("test"))'

# Export to file
ax datasets export ds_xyz789
```

### Environment Variables

The CLI respects these environment variables:

- `ARIZE_API_KEY`: Your Arize API key
- `ARIZE_REGION`: Region (US, EU, etc.)
- `ARIZE_PROXY_URL`: AX-specific HTTP CONNECT proxy URL (highest precedence)
- `HTTPS_PROXY` / `https_proxy`, `HTTP_PROXY` / `http_proxy`,
  `ALL_PROXY` / `all_proxy`: Standard proxy URLs (lowercase wins;
  non-`http://` schemes are skipped with a warning)
- `ARIZE_NO_PROXY`, then `NO_PROXY` / `no_proxy`: Comma-separated proxy
  bypass hosts
- `ARIZE_SSL_CA_CERT`, then `REQUESTS_CA_BUNDLE`, then `SSL_CERT_FILE`:
  CA bundle for TLS-inspecting proxy certificates
- `grpc_proxy` / `no_grpc_proxy`: Set by the CLI for Arrow Flight and
  OTLP/gRPC; your own values are preserved in `system` proxy mode
- Any other `ARIZE_*` variables will be detected during `ax profiles create`

### Debugging

Enable verbose mode to see detailed SDK logs:

```bash
ax datasets list --space sp_abc123 --verbose
```

## Troubleshooting

### Configuration Issues

**Problem**: `Profile 'default' not found.`

**Solution**: Run `ax profiles create` to create a configuration profile.

---

**Problem**: `Invalid API key`

**Solution**: Verify your API key:

1. Check your configuration: `ax profiles show`
2. Refresh your API key from the Arize UI
3. Update your profile: `ax profiles update --api-key <new-key>`

---

### Connection Issues

**Problem**: `Connection refused` or `SSL errors`

**Solution**:

1. Check your routing configuration: `ax profiles show`
2. Verify network connectivity
3. For on-premise installations, ensure `single_host` is configured correctly
4. Configure `[network]` or `HTTPS_PROXY` for corporate egress proxies
5. Set `network.ca_bundle` / `ARIZE_SSL_CA_CERT` for a TLS-inspecting proxy
6. For SSL issues, check `security.request_verify` setting (use with caution)

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
ax profiles --help
```

### Support

- **Documentation**: [https://arize.com/docs/api-clients/cli/](https://arize.com/docs/api-clients/cli/)
- **Bug Reports**: [GitHub Issues](https://github.com/Arize-ai/arize-ax-cli/issues)
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
