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
  - [Experiments](#experiments)
  - [Projects](#projects)
  - [Prompts](#prompts)
  - [Skills](#skills)
  - [Spans](#spans)
  - [Tasks](#tasks)
  - [Traces](#traces)
- [Usage Examples](#usage-examples)
  - [Creating a Dataset from a CSV File](#creating-a-dataset-from-a-csv-file)
  - [Creating a Dataset from stdin](#creating-a-dataset-from-stdin)
  - [Exporting Dataset List to JSON](#exporting-dataset-list-to-json)
  - [Exporting Dataset Examples](#exporting-dataset-examples)
  - [Exporting Experiment Runs](#exporting-experiment-runs)
  - [Exporting Spans by Trace ID](#exporting-spans-by-trace-id)
  - [Using a Different Profile for a Command](#using-a-different-profile-for-a-command)
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
- **Spans & Traces**: Query and filter LLM spans and traces
- **Agent Skills**: Install Arize context skills for AI coding agents (Claude Code, Cursor, Codex, Windsurf)
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
ax profiles update --profile staging --region EU

# Use a specific profile for a single command
ax datasets list --profile production

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
ax datasets <TAB> # Shows dataset subcommands (list, get, export, create, append, delete)
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

- `--profile, -p <name>`: Use a specific configuration profile
- `--output, -o <format>`: Set output format (`table`, `json`, `csv`, `parquet`, or a file path)
- `--help, -h`: Show help message

> **Note:** `--verbose, -v` is available on each individual subcommand (e.g., `ax datasets list --verbose`) rather than as a top-level flag.

### AI Integrations

Configure external LLM providers for use within the Arize platform (for evaluations, online evals, and more):

```bash
# List AI integrations
ax ai-integrations list [--name <substring>] [--space <space>] [--limit 15] [--cursor <cursor>]

# Get a specific integration
ax ai-integrations get <integration>

# Create an integration (OpenAI example)
ax ai-integrations create --name "OpenAI Prod" --provider openAI \
  --api-key <key> --model-name gpt-4o --model-name gpt-4o-mini

# Create an integration with custom headers
ax ai-integrations create --name "Custom LLM" --provider custom \
  --base-url https://my-llm.example.com \
  --headers-json '{"X-API-Key": "secret"}'

# Create an AWS Bedrock integration
ax ai-integrations create --name "Bedrock" --provider awsBedrock \
  --provider-metadata-json '{"role_arn": "arn:aws:iam::123456789:role/MyRole"}'

# Update an integration
ax ai-integrations update <integration> --name "Renamed" --api-key <new-key>

# Delete an integration
ax ai-integrations delete <integration> [--force]
```

**Supported providers:**

| Provider      | Value         | Notes                                        |
| ------------- | ------------- | -------------------------------------------- |
| OpenAI        | `openAI`      |                                              |
| Azure OpenAI  | `azureOpenAI` | Use `--base-url` for the deployment endpoint |
| AWS Bedrock   | `awsBedrock`  | Requires `--provider-metadata-json`          |
| Vertex AI     | `vertexAI`    | Requires `--provider-metadata-json`          |
| Anthropic     | `anthropic`   |                                              |
| NVIDIA NIM    | `nvidiaNim`   |                                              |
| Google Gemini | `gemini`      |                                              |
| Custom        | `custom`      | Use `--base-url` for a custom endpoint       |

### Annotation Configs

Manage annotation configs (rubrics for human and automated evaluation):

```bash
# List annotation configs
ax annotation-configs list [--name <substring>] [--space <space>] [--limit 15] [--cursor <cursor>]

# Get a specific annotation config
ax annotation-configs get <annotation-config>

# Create a freeform annotation config (free-text feedback)
ax annotation-configs create --name "Quality" --space <space> --type freeform

# Create a continuous annotation config (numeric score range)
ax annotation-configs create --name "Score" --space <space> --type continuous \
  --min-score 0 --max-score 1 --optimization-direction maximize

# Create a categorical annotation config (discrete labels)
ax annotation-configs create --name "Verdict" --space <space> --type categorical \
  --value good --value neutral --value bad --optimization-direction maximize

# Delete an annotation config
ax annotation-configs delete <annotation-config> [--force]
```

**Supported annotation config types:**

| Type          | Required options                                                        | Optional options           |
| ------------- | ----------------------------------------------------------------------- | -------------------------- |
| `freeform`    | _(none)_                                                                | —                          |
| `continuous`  | `--min-score`, `--max-score`                                            | `--optimization-direction` |
| `categorical` | `--value` (repeat for multiple labels, e.g. `--value good --value bad`) | `--optimization-direction` |

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
  --assignment-method random

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
```

**Assignment methods:**

| Method   | Behavior                                      |
| -------- | --------------------------------------------- |
| `all`    | Every annotator is assigned to every record (default) |
| `random` | Each record is randomly assigned to one annotator |

### API Keys

> **Security note:** The raw key value is only returned once (on `create` and `refresh`). Store it securely immediately — it cannot be retrieved again.

```bash
# List API keys
ax api-keys list [--key-type user|service] [--status active|deleted] \
  [--limit 15] [--cursor <cursor>]

# Create a user key (authenticates as you)
ax api-keys create --name "My Key" [--description "..."] [--expires-at 2025-12-31T23:59:59]

# Create a service key (scoped to a space)
ax api-keys create --name "CI Key" --key-type service --space-id <space-id>

# Refresh a key (revokes old key, issues replacement)
ax api-keys refresh <key-id> [--expires-at 2025-12-31T23:59:59]

# Delete a key
ax api-keys delete <key-id> [--force]
```

**Key types:**

| Type      | Description                                                             |
| --------- | ----------------------------------------------------------------------- |
| `user`    | Authenticates as the creating user. Global, so `--space-id` not needed. |
| `service` | Scoped to a specific space. `--space-id` is required.                  |

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

# Create a new evaluator
ax evaluators create \
  --name "Response Relevance" \
  --space <space> \
  --commit-message "Initial version" \
  --template-name relevance \
  --template "Is this response relevant to the query? {{input}} {{output}}" \
  --ai-integration-id <integration-id> \
  --model-name gpt-4o

# Create a classification evaluator (label → numeric score; omit flag for freeform)
ax evaluators create \
  --name "Relevance classifier" \
  --space <space> \
  --commit-message "Initial version" \
  --template-name relevance \
  --template "Classify: {{output}}" \
  --ai-integration-id <integration-id> \
  --model-name gpt-4o \
  --classification-choices '{"relevant":1,"irrelevant":0}' \
  --direction maximize \
  --data-granularity span

# Update evaluator metadata
ax evaluators update <evaluator> --name "New Name"
ax evaluators update <evaluator> --description "Updated description"

# Delete an evaluator (and all its versions)
ax evaluators delete <evaluator> [--force]

# List all versions of an evaluator
ax evaluators list-versions <evaluator-id> [--limit 15] [--cursor <cursor>]

# Get a specific version by ID
ax evaluators get-version <version-id>

# Create a new version of an existing evaluator
ax evaluators create-version <evaluator-id> \
  --commit-message "Improved prompt" \
  --template-name relevance \
  --template "Rate the relevance of the response: {{input}} {{output}}" \
  --ai-integration-id <integration-id> \
  --model-name gpt-4o

# Same optional template fields as create (e.g. classification choices)
ax evaluators create-version <evaluator-id> \
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

### Experiments

Run and analyze experiments on your datasets:

```bash
# List experiments (optionally filtered by dataset)
ax experiments list [--dataset <dataset>] [--limit 15] [--cursor <cursor>]

# Get a specific experiment
ax experiments get <experiment>

# Export all runs from an experiment
ax experiments export <experiment> [--output-dir .] [--stdout]

# Create a new experiment from a data file
ax experiments create --name "My Experiment" --dataset <dataset> --file runs.csv

# Create an experiment from stdin
ax experiments create --name "My Experiment" --dataset <dataset> --file -

# List runs for an experiment
ax experiments list_runs <experiment> [--limit 30]

# Delete an experiment
ax experiments delete <experiment> [--force]
```

> **Note:** The data file for `experiments create` must contain `example_id` and `output` columns. Extra columns are passed through as additional fields.

**Export options:**

| Option            | Description                                    |
| ----------------- | ---------------------------------------------- |
| `--output-dir`    | Output directory (default: current directory)  |
| `--stdout`        | Print JSON to stdout instead of saving to file |
| `--profile`, `-p` | Configuration profile to use                   |
| `--verbose`, `-v` | Enable verbose logs                            |

### Projects

Organize your projects:

```bash
# List projects
ax projects list [--name <substring>] [--space <space>] [--limit 15] [--cursor <cursor>]

# Get project metadata
ax projects get <project>

# Create a new project
ax projects create --name "My Project" --space <space>

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
  --provider openAI \
  --input-variable-format f_string \
  --messages messages.json \
  --commit-message "Initial version"

# Update a prompt's description
ax prompts update <prompt> --description "Updated description"

# Delete a prompt (removes all versions)
ax prompts delete <prompt> [--force]

# List versions for a prompt
ax prompts list-versions <prompt> [--limit 15] [--cursor <cursor>]

# Create a new version
ax prompts create-version <prompt> \
  --provider openAI \
  --input-variable-format f_string \
  --messages messages_v2.json \
  --commit-message "Improved system prompt"

# Create a new version (inline messages JSON)
ax prompts create-version <prompt> \
  --provider openAI \
  --input-variable-format f_string \
  --messages '[{"role": "user", "content": "Your prompt here"}]' \
  --commit-message "Minimal inline JSON example"


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
  {"role": "system", "content": "You are a helpful assistant."},
  {"role": "user",   "content": "Summarize the following: {text}"},
  {"role": "assistant", "tool_calls": [{"id": "tool-call-1", "type": "function", "function": {"name": "search", "arguments": "{\"query\": \"summarize {text}\"}}]},
  {"role": "tool", "tool_call_id": "tool-call-1", "content": "This is the result of the search function."},
]
```

**Input variable formats:**

| Format     | Syntax              |
| ---------- | ------------------- |
| `f_string` | `{variable_name}`   |
| `mustache` | `{{variable_name}}` |
| `none`     | No variable parsing |

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
| `--profile`, `-p` | Configuration profile to use                                          |
| `--verbose`, `-v` | Enable verbose logs                                                   |

**Examples:**

```bash
ax spans export <project-id> --filter "status_code = 'ERROR'"
ax spans export <project-id> --filter "latency_ms > 1000"
ax spans export <project-id> --trace-id abc123 --filter "latency_ms > 1000"
ax spans export <project-id> --start-time 2024-01-01T00:00:00Z --end-time 2024-01-02T00:00:00Z
```

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

### Tasks

Manage evaluation tasks and trigger on-demand runs:

```bash
# List tasks (optionally filtered by space, project, dataset, or type)
ax tasks list [--name <substring>] [--space <space>] [--project-id <project-name-or-id>] \
  [--dataset-id <dataset-id>] [--task-type template_evaluation|code_evaluation] \
  [--limit 15] [--cursor <cursor>]

# Get a specific task
ax tasks get <task-id>

# Create a project-based task (use ax evaluators list to find evaluator IDs)
ax tasks create \
  --name "Relevance Check" \
  --task-type template_evaluation \
  --evaluators '[{"evaluator_id": "<id from ax evaluators list>", "query_filter": null, "column_mappings": null}]' \
  --project <project> [--space <space>] \
  --is-continuous

# Create a dataset-based task
ax tasks create \
  --name "Dataset Eval" \
  --task-type template_evaluation \
  --evaluators '[{"evaluator_id": "<evaluator-id>"}]' \
  --dataset <dataset> \
  --experiment-ids <exp-id-1>,<exp-id-2>

# Trigger an on-demand run
ax tasks trigger-run <task-id>

# Trigger a run and wait for it to complete
ax tasks trigger-run <task-id> --wait

# Trigger a run over a specific data window
ax tasks trigger-run <task-id> \
  --data-start-time 2024-01-01T00:00:00Z \
  --data-end-time 2024-01-02T00:00:00Z \
  --max-spans 5000

# List runs for a task (optionally filtered by status)
ax tasks list-runs <task-id> [--status pending|running|completed|failed|cancelled] \
  [--limit 15] [--cursor <cursor>]

# Get a specific run
ax tasks get-run <run-id>

# Cancel a run (only valid when pending or running)
ax tasks cancel-run <run-id> [--force]

# Wait for a run to reach a terminal state
ax tasks wait-for-run <run-id> [--poll-interval 5] [--timeout 600]
```

**`create` options:**

| Option | Description |
| --- | --- |
| `--name`, `-n` | Task name (must be unique within the space) |
| `--task-type` | `template_evaluation` or `code_evaluation` |
| `--evaluators` | JSON array of evaluator configs. Get IDs via `ax evaluators list`. Example: `[{"evaluator_id": "<id>", "query_filter": null, "column_mappings": null}]`. Fields: `evaluator_id` (required), `query_filter` (optional per-evaluator filter), `column_mappings` (optional column name remappings) |
| `--project` | Project name or ID; mutually exclusive with `--dataset` |
| `--space` | Space name or ID (helps resolve project/dataset names) |
| `--dataset` | Dataset name or ID; mutually exclusive with `--project` |
| `--experiment-ids` | Comma-separated experiment IDs (required for dataset-based tasks) |
| `--sampling-rate` | Fraction of data to evaluate (0–1); project tasks only |
| `--is-continuous` / `--no-continuous` | Run continuously on incoming data |
| `--query-filter` | Task-level filter applied to all evaluators |

**`trigger-run` options:**

| Option | Description |
| --- | --- |
| `--data-start-time` | ISO 8601 start of the data window |
| `--data-end-time` | ISO 8601 end of the data window (defaults to now) |
| `--max-spans` | Maximum spans to evaluate (default: 10 000) |
| `--override-evaluations` | Re-evaluate data that already has labels |
| `--experiment-ids` | Comma-separated experiment IDs; dataset-based tasks only |
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
| `--profile`, `-p` | Configuration profile to use                                            |
| `--verbose`, `-v` | Enable verbose logs                                                     |

**Filter examples:**

```bash
ax traces list <project-id> --filter "status_code = 'ERROR'"
ax traces list <project-id> --start-time 2024-01-01T00:00:00Z
ax traces list <project-id> --filter "latency_ms > 5000" --limit 50
```

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

### Using a Different Profile for a Command

```bash
ax datasets list --space sp_abc123 --profile production
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
