# Changelog

## [0.29.0](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.28.1...arize-ax-cli/v0.29.0) (2026-08-06)


### 🎁 New Features

* forward hidden --utm-params through profiles create ([#82304](https://github.com/Arize-ai/arize/issues/82304)) ([84840f2](https://github.com/Arize-ai/arize/commit/84840f232cd7dbf0defef8aa6f8b6be9aa1e6670))


### 💫 Code Refactoring

* remove CLI cache configuration ([#82168](https://github.com/Arize-ai/arize/issues/82168)) ([2501aa2](https://github.com/Arize-ai/arize/commit/2501aa27e2467b086d395982af603a988469f035))

## [0.28.1](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.28.0...arize-ax-cli/v0.28.1) (2026-08-05)


### 🐛 Bug Fixes

* **oauth:** preserve signup attribution through login ([#81170](https://github.com/Arize-ai/arize/issues/81170)) ([47b33f9](https://github.com/Arize-ai/arize/commit/47b33f95d02bcd0e4080beb7a7c82eb6766165b5))

## [0.28.0](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.27.1...arize-ax-cli/v0.28.0) (2026-08-03)


### 🎁 New Features

* write API keys to dotenv files ([#81125](https://github.com/Arize-ai/arize/issues/81125)) ([28ffd1c](https://github.com/Arize-ai/arize/commit/28ffd1c3c5cfc2039e146cdd5b4f52fac488200f))

## [0.27.1](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.27.0...arize-ax-cli/v0.27.1) (2026-07-28)


### ❔ Miscellaneous Chores

* Bump CLI arize dependency to 8.43.1 ([#80864](https://github.com/Arize-ai/arize/issues/80864)) ([1ee945e](https://github.com/Arize-ai/arize/commit/1ee945e2663e0217debed5e1627f53a926c55c2e))

## [0.27.0](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.26.0...arize-ax-cli/v0.27.0) (2026-07-22)


### 🎁 New Features

* **annotation-configs:** add update command ([#79603](https://github.com/Arize-ai/arize/issues/79603)) ([28606ec](https://github.com/Arize-ai/arize/commit/28606ecb697c10bc85bff878ef1cbb6167d69fc2))
* **service-keys:** update create-service-key for new SDK orgs/spaces bindings API ([#80155](https://github.com/Arize-ai/arize/issues/80155)) ([4c1e5dc](https://github.com/Arize-ai/arize/commit/4c1e5dc24784c62f0430719a60d58066be2d5388))
* **datasets:** add delete-examples command ([#79602](https://github.com/Arize-ai/arize/issues/79602)) ([c30e294](https://github.com/Arize-ai/arize/commit/c30e2944d43d7aa929f6de42638b86218fe9ac16))
* **datasets:** add update examples function ([#78671](https://github.com/Arize-ai/arize/issues/78671)) ([57e993f](https://github.com/Arize-ai/arize/commit/57e993f007c0d452acc43515cfdd32fc28ba7ecc))
* **resource-restrictions:** add list command ([#79601](https://github.com/Arize-ai/arize/issues/79601)) ([fc71bc3](https://github.com/Arize-ai/arize/commit/fc71bc3c8d40072937f786b5a6bc22ec7998024f))


### 🐛 Bug Fixes

* assume UTC for naive datetimes across all CLI commands ([#79024](https://github.com/Arize-ai/arize/issues/79024)) ([3632b93](https://github.com/Arize-ai/arize/commit/3632b939ecee13e87a58dc77b9c6cc9e3fa04cd5))

## [0.26.0](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.25.1...arize-ax-cli/v0.26.0) (2026-07-17)

> **Minor release.** The v2 REST API standardization ([#78907](https://github.com/Arize-ai/arize/pull/78907)) is technically breaking, but **only affects endpoints/methods in `alpha` or `beta`** — all gated behind the pre-release opt-in and documented with a warning. **No stable surface changes.**

### ⚠ BREAKING CHANGES (pre-release only)

* **enums:** standardize all enum values to `SCREAMING_SNAKE_CASE` — AI integrations, prompts, evaluators, tasks, orgs, spaces, users, API keys, and roles ([#78718](https://github.com/Arize-ai/arize/issues/78718), [#78720](https://github.com/Arize-ai/arize/issues/78720), [#78721](https://github.com/Arize-ai/arize/issues/78721), [#78722](https://github.com/Arize-ai/arize/issues/78722)) ([b17b78d](https://github.com/Arize-ai/arize/commit/b17b78d6a68bf8a6e0736df251a73a9dc0c33cab))
* **types:** apply type-naming convention across dataset, org/space/user, access-control, and API-key/audit-log schemas ([#78740](https://github.com/Arize-ai/arize/issues/78740), [#79098](https://github.com/Arize-ai/arize/issues/79098), [#79101](https://github.com/Arize-ai/arize/issues/79101), [#79099](https://github.com/Arize-ai/arize/issues/79099)) ([b17b78d](https://github.com/Arize-ai/arize/commit/b17b78d6a68bf8a6e0736df251a73a9dc0c33cab))
* **openapi:** enforce verb-first `operationId` naming (`*ListResponse` → `List*Response`), incl. annotation-config & evaluator-version request schemas ([#79270](https://github.com/Arize-ai/arize/issues/79270), [#79433](https://github.com/Arize-ai/arize/issues/79433)) ([b17b78d](https://github.com/Arize-ai/arize/commit/b17b78d6a68bf8a6e0736df251a73a9dc0c33cab))
* **prompts:** `set-prompt-version-labels` now returns the full `PromptVersion` ([#79278](https://github.com/Arize-ai/arize/issues/79278)) ([b17b78d](https://github.com/Arize-ai/arize/commit/b17b78d6a68bf8a6e0736df251a73a9dc0c33cab))

### 🎁 New Features

* **api:** return `404` for list endpoints when the scoped resource is missing or inaccessible ([#79279](https://github.com/Arize-ai/arize/issues/79279)) ([b17b78d](https://github.com/Arize-ai/arize/commit/b17b78d6a68bf8a6e0736df251a73a9dc0c33cab))
* **openapi:** enforce naming conventions and extract shared nested schemas ([#79103](https://github.com/Arize-ai/arize/issues/79103)) ([b17b78d](https://github.com/Arize-ai/arize/commit/b17b78d6a68bf8a6e0736df251a73a9dc0c33cab))
* **spectral:** enforce lockstep naming and strict nested-schema lint rules ([#79280](https://github.com/Arize-ai/arize/issues/79280)) ([b17b78d](https://github.com/Arize-ai/arize/commit/b17b78d6a68bf8a6e0736df251a73a9dc0c33cab))

### 🐛 Bug Fixes

* **ci:** fix the OpenAPI lint check ([#78913](https://github.com/Arize-ai/arize/issues/78913)) ([b17b78d](https://github.com/Arize-ai/arize/commit/b17b78d6a68bf8a6e0736df251a73a9dc0c33cab))
* **openapi:** resolve follow-up gaps from the REST API audit ([#79440](https://github.com/Arize-ai/arize/issues/79440)) ([b17b78d](https://github.com/Arize-ai/arize/commit/b17b78d6a68bf8a6e0736df251a73a9dc0c33cab))
* **annotation-configs:** migrate create command to arize SDK 8.40 ([#78795](https://github.com/Arize-ai/arize/issues/78795)) ([24bf711](https://github.com/Arize-ai/arize/commit/24bf711b9137482b94550cf268256fcbab20a6da))

### ❔ Miscellaneous Chores

* promote pre-release stage from `alpha` to `beta` ([#78707](https://github.com/Arize-ai/arize/issues/78707)) ([b17b78d](https://github.com/Arize-ai/arize/commit/b17b78d6a68bf8a6e0736df251a73a9dc0c33cab))

---

## Migration notes — pre-release (`alpha`/`beta`) commands only

The recasing flows from the OpenAPI spec into the CLI. **Command and flag names are unchanged** — what changed are the **enum values you pass** to flags (and inside inline JSON). Old-cased values are now rejected.

**Flag values → `SCREAMING_SNAKE_CASE`:**

| Command / flag | Before | After |
|---|---|---|
| `ai-integrations --provider` | `open_ai`, `azureOpenAI`, `awsBedrock`, `vertexAI`, `nvidiaNim`, `gemini`, `anthropic`, `custom` | `OPEN_AI`, `AZURE_OPEN_AI`, `AWS_BEDROCK`, `VERTEX_AI`, `NVIDIA_NIM`, `GEMINI`, `ANTHROPIC`, `CUSTOM` |
| `annotation-configs --type` | `freeform`, `continuous`, `categorical` | `FREEFORM`, `CONTINUOUS`, `CATEGORICAL` |
| `--optimization-direction` | `maximize`, `minimize`, `none` | `MAXIMIZE`, `MINIMIZE`, `NONE` |
| `--assignment-method` | `all`, `random` | `ALL`, `RANDOM` |
| `api-keys --key-type` | `user`, `service` | `USER`, `SERVICE` |
| `api-keys --status` | `active`, `revoked` | `ACTIVE`, `REVOKED` |
| `evaluators --data-granularity` | `span`, `trace`, `session` | `SPAN`, `TRACE`, `SESSION` |
| `evaluators --code-type` | `managed`, `custom` | `MANAGED`, `CUSTOM` |
| `evaluators --managed-evaluator` | `MatchesRegex`, `JSONParseable`, `ContainsAnyKeyword`, `ContainsAllKeywords`, `ExactMatch` | `MATCHES_REGEX`, `JSON_PARSEABLE`, `CONTAINS_ANY_KEYWORD`, `CONTAINS_ALL_KEYWORDS`, `EXACT_MATCH` |
| `prompts --input-variable-format` | `f_string`, `mustache`, `none` | `F_STRING`, `MUSTACHE`, `NONE` |
| `tasks --task-type` | `template_evaluation`, `code_evaluation`, `run_experiment` | `TEMPLATE_EVALUATION`, `CODE_EVALUATION`, `RUN_EXPERIMENT` |
| `tasks list-runs --status` | `pending`, `running`, `completed`, `failed`, `cancelled` | `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED` |
| `users --status` | `active`, `invited`, `expired` | `ACTIVE`, `INVITED`, `EXPIRED` |
| `users --role` | `admin`, `member`, `annotator` | `ADMIN`, `MEMBER`, `ANNOTATOR` |
| `users --invite-mode` | `email_link`, `temporary_password`, `none` | `EMAIL_LINK`, `TEMPORARY_PASSWORD`, `NONE` |

**Inline JSON payloads use the new casing too:**

* `prompts --messages`: `role` → `"SYSTEM"` / `"USER"` / `"ASSISTANT"` / `"TOOL"`; tool-call `type` → `"FUNCTION"`.
* `annotation-queues --record-sources`: `record_type` → `"SPAN"` / `"EXAMPLE"`.
* `tasks` experiment config: `experiment_type` → `"LLM_GENERATION"`; `input_variable_format` → `"MUSTACHE"` / `"F_STRING"`.

## [0.25.1](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.25.0...arize-ax-cli/v0.25.1) (2026-07-10)


### 🐛 Bug Fixes

* fix pydantic validation error for limit ([#78246](https://github.com/Arize-ai/arize/issues/78246)) ([3f2a067](https://github.com/Arize-ai/arize/commit/3f2a067506ef7b96a14742be7619761b58d5503b))

## [0.25.0](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.24.1...arize-ax-cli/v0.25.0) (2026-06-12)


### 🎁 New Features

* **api-keys:** add revoke support ([#74112](https://github.com/Arize-ai/arize/issues/74112)) ([28198d3](https://github.com/Arize-ai/arize/commit/28198d3ee3e72502016af6b10b8ba2b98fcbbbd5))

### 🐛 Bug Fixes

* **oauth:** include `single_port` in OAuth app URL generation ([#74902](https://github.com/Arize-ai/arize/issues/74902)) ([96cd3e1](https://github.com/Arize-ai/arize/commit/96cd3e171aa4240e78c5c728e6e5928735e8e5e6))

### 💫 Code Refactoring

* **api-keys:** removed delete method ([#74112](https://github.com/Arize-ai/arize/issues/74112)) ([28198d3](https://github.com/Arize-ai/arize/commit/28198d3ee3e72502016af6b10b8ba2b98fcbbbd5))

## [0.24.1](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.24.0...arize-ax-cli/v0.24.1) (2026-06-10)


### ❔ Miscellaneous Chores

* add default CLI identity headers into SDK configuration ([#74483](https://github.com/Arize-ai/arize/issues/74483)) ([7ceedac](https://github.com/Arize-ai/arize/commit/7ceedac6cc06f93483f36026ae28eca43479a621))

## [0.24.0](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.23.0...arize-ax-cli/v0.24.0) (2026-06-08)


### 🎁 New Features

* **auth:** enable OAuth on Flight-backed export commands ([#74194](https://github.com/Arize-ai/arize/issues/74194)) ([a7c2cd3](https://github.com/Arize-ai/arize/commit/a7c2cd311cb9914d3bd38287a93ff497fd39c7b3)), closes [#71530](https://github.com/Arize-ai/arize/issues/71530)
* **api-keys:** add grace period support to API key refresh ([#73351](https://github.com/Arize-ai/arize/issues/73351)) ([307a733](https://github.com/Arize-ai/arize/commit/307a7339a844571431af64c878d6ee55ae758ae6))

## [0.23.0](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.22.0...arize-ax-cli/v0.23.0) (2026-06-05)


### 🎁 New Features

* **annotation-queues:** Add add-records command ([#73116](https://github.com/Arize-ai/arize/issues/73116)) ([5201e30](https://github.com/Arize-ai/arize/commit/5201e30dab39fe373eaa0cceb11b2c74769c933e))
* **experiments:** Add list-runs command ([#73116](https://github.com/Arize-ai/arize/issues/73116)) ([5201e30](https://github.com/Arize-ai/arize/commit/5201e30dab39fe373eaa0cceb11b2c74769c933e))
* **organizations:** Add delete command ([#73116](https://github.com/Arize-ai/arize/issues/73116)) ([5201e30](https://github.com/Arize-ai/arize/commit/5201e30dab39fe373eaa0cceb11b2c74769c933e))
* **projects:** Add update command ([#73318](https://github.com/Arize-ai/arize/issues/73318)) ([8fa395a](https://github.com/Arize-ai/arize/commit/8fa395af07d713706afe24d0d34ed3f6547f26fb))
* **prompts:** Add missing invocation & provider params ([#73116](https://github.com/Arize-ai/arize/issues/73116)) ([5201e30](https://github.com/Arize-ai/arize/commit/5201e30dab39fe373eaa0cceb11b2c74769c933e))
* **spans:** Add delete command ([#73116](https://github.com/Arize-ai/arize/issues/73116)) ([5201e30](https://github.com/Arize-ai/arize/commit/5201e30dab39fe373eaa0cceb11b2c74769c933e))
* **users:** Add delete command ([#73116](https://github.com/Arize-ai/arize/issues/73116)) ([5201e30](https://github.com/Arize-ai/arize/commit/5201e30dab39fe373eaa0cceb11b2c74769c933e))

## [0.22.0](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.21.0...arize-ax-cli/v0.22.0) (2026-05-30)


### 🎁 New Features

* **output:** enhance table formatting with no-wrap tokens and natural-width rendering ([#73062](https://github.com/Arize-ai/arize/issues/73062)) ([946e5b3](https://github.com/Arize-ai/arize/commit/946e5b35c8c65ac4b9789c3a084c9c9c82e0892c))

## [0.21.0](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.20.0...arize-ax-cli/v0.21.0) (2026-05-27)


### 🎁 New Features

* **annotations:** add batch annotate commands for spans, datasets, and experiments ([#71998](https://github.com/Arize-ai/arize/issues/71998)) ([0eea49b](https://github.com/Arize-ai/arize/commit/0eea49b2a2ccda69f14a09fe35d674724dd5f82c))
* **datasets:** add 'ax datasets update' command ([#72272](https://github.com/Arize-ai/arize/issues/72272)) ([c93869c](https://github.com/Arize-ai/arize/commit/c93869c22b287aaef3cb7e2acd1f23486291411c))

### 🐛 Bug Fixes

* resolve type-check errors in evaluators and annotation-queues ([c93869c](https://github.com/Arize-ai/arize/commit/c93869c22b287aaef3cb7e2acd1f23486291411c))
* resolve type-check errors in users, api-keys, evaluators, annotation-configs, tasks ([#72432](https://github.com/Arize-ai/arize/issues/72432)) ([ea899a1](https://github.com/Arize-ai/arize/commit/ea899a1ad478deafd9d3a14123ddd3cb90492860))
* **rest-api:** use base64 Relay global IDs in OpenAPI spec examples ([#71993](https://github.com/Arize-ai/arize/issues/71993)) ([5903e5b](https://github.com/Arize-ai/arize/commit/5903e5b6bea4b149906f1fc45eb7aa8993eac2c9)), closes [#71246](https://github.com/Arize-ai/arize/issues/71246)
* update output parsing for easier to read table outputs ([c93869c](https://github.com/Arize-ai/arize/commit/c93869c22b287aaef3cb7e2acd1f23486291411c))

## [0.20.0](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.19.0...arize-ax-cli/v0.20.0) (2026-05-14)


### 🎁 New Features

* **profile-setup:** prompt for URL scheme and apply app_scheme for single-host URLs ([#71936](https://github.com/Arize-ai/arize/issues/71936)) ([debec39](https://github.com/Arize-ai/arize/commit/debec3944333f79b410616ea4d606508bb41b7a8))

## [0.19.0](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.18.0...arize-ax-cli/v0.19.0) (2026-05-13)


### 🎁 New Features

* **tasks:** add run_experiment support (PR [#70545](https://github.com/Arize-ai/arize/issues/70545) follow-on) ([#71360](https://github.com/Arize-ai/arize/issues/71360)) ([b117d5e](https://github.com/Arize-ai/arize/commit/b117d5e57d24c3df58bc4cca159c6e117598a59c))
* **users:** add user management commands ([#71316](https://github.com/Arize-ai/arize/issues/71316)) ([b5a7ed4](https://github.com/Arize-ai/arize/commit/b5a7ed4a8c66f091605eff1dba37662bea8c12da)), closes [#70418](https://github.com/Arize-ai/arize/issues/70418)

## [0.18.0](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.17.1...arize-ax-cli/v0.18.0) (2026-05-08)


### ⚠ BREAKING CHANGES

* **commands:** remove per-command --profile flag ([#70966](https://github.com/Arize-ai/arize/issues/70966))

### 🎁 New Features

* **auth:** add browser-based OAuth PKCE login with token refresh and profile integration ([#70318](https://github.com/Arize-ai/arize/issues/70318)) ([3261fd2](https://github.com/Arize-ai/arize/commit/3261fd26cf6f480fbac860f03e772dcd689ce322))

## [0.17.1](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.17.0...arize-ax-cli/v0.17.1) (2026-05-07)


### 🐛 Bug Fixes

* **sdk:** respect request_verify for REST API commands ([#69838](https://github.com/Arize-ai/arize/issues/69838)) ([31b8f3c](https://github.com/Arize-ai/arize/commit/31b8f3c4915f5b5e6fb6cd5ba695501a0ff84e63))
* use kwargs-building pattern for annotation-queues update command ([#69708](https://github.com/Arize-ai/arize/issues/69708)) ([1b2ab35](https://github.com/Arize-ai/arize/commit/1b2ab3513b4b83cae6d51714db1265d9952e9255))

## [0.17.0](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.16.0...arize-ax-cli/v0.17.0) (2026-05-01)


### 🎁 New Features

* **evaluators:** add code evaluator support to ax evaluators create ([#69652](https://github.com/Arize-ai/arize/issues/69652)) ([0771f19](https://github.com/Arize-ai/arize/commit/0771f19da0ed793e66a44d88eea32a24c6b34a38))

## [0.16.0](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.15.0...arize-ax-cli/v0.16.0) (2026-04-29)


### 🎁 New Features

* **tasks:** add ax tasks update and ax tasks delete commands ([#69117](https://github.com/Arize-ai/arize/issues/69117)) ([ac367cf](https://github.com/Arize-ai/arize/commit/ac367cf9152615f72ab34be91f2aca85b45ac2db))
* **types:** use public SDK types instead of _generated imports ([#69711](https://github.com/Arize-ai/arize/issues/69711)) ([029f151](https://github.com/Arize-ai/arize/commit/029f15199fbb7c78983ba5a79d6e44142c5e62ae))


### 🐛 Bug Fixes

* surface failed experiment run errors in export command ([#69698](https://github.com/Arize-ai/arize/issues/69698)) ([2c41178](https://github.com/Arize-ai/arize/commit/2c411784bde5af4eb43c2ef5e0d5368f5269082d))


### ❔ Miscellaneous Chores

* **deps-dev:** bump pytest from 8.4.2 to 9.0.3 in /sdk/python/arize-ax-cli ([#69533](https://github.com/Arize-ai/arize/issues/69533)) ([a56443d](https://github.com/Arize-ai/arize/commit/a56443dc42e6efc7dcfc120dac78b2253ea308e0))
* **deps-dev:** bump pytest from 8.4.2 to 9.0.3 in /sdk/python/arize-ax-cli ([#69878](https://github.com/Arize-ai/arize/issues/69878)) ([335afa0](https://github.com/Arize-ai/arize/commit/335afa044e0069ec5148c8cb9308436a66d6ce35))

## [0.15.0](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.14.0...arize-ax-cli/v0.15.0) (2026-04-26)


### 🎁 New Features

* update optimization direction enum to include none ([#67047](https://github.com/Arize-ai/arize/issues/67047)) ([b948295](https://github.com/Arize-ai/arize/commit/b948295822a80a6c28a8fa2afa3a60e0176111b1))


### 🐛 Bug Fixes

* **ax-cli:** update LlmProvider enum values to snake_case (follows [#68525](https://github.com/Arize-ai/arize/issues/68525)) ([#69410](https://github.com/Arize-ai/arize/issues/69410)) ([138f31d](https://github.com/Arize-ai/arize/commit/138f31d841a793a6cc6a9bf3b4fd844784f28d13))
* **onlinetasksrunner:** populate DatasetId from experiment for CLI-triggered evals ([#68775](https://github.com/Arize-ai/arize/issues/68775)) ([2118121](https://github.com/Arize-ai/arize/commit/21181211c6b11b64d5254201bd5c5daa40698bd9)), closes [#68756](https://github.com/Arize-ai/arize/issues/68756)

## [0.14.0](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.13.0...arize-ax-cli/v0.14.0) (2026-04-17)


### 🎁 New Features

* **cli:** implement background update check and upgrade command ([#68835](https://github.com/Arize-ai/arize/issues/68835)) ([a607303](https://github.com/Arize-ai/arize/commit/a607303de5096563d07eee2e268a56fed4bfc691))
* **config:** enhance profile management and add exception handling tests ([#68936](https://github.com/Arize-ai/arize/issues/68936)) ([26855ad](https://github.com/Arize-ai/arize/commit/26855adcabf9b2ea1fecb9385efb685a823d5bcc))
* **config:** handle empty default profile, allow deleting default, and enforce load errors ([#68860](https://github.com/Arize-ai/arize/issues/68860)) ([bc1887b](https://github.com/Arize-ai/arize/commit/bc1887b04b74017d5899ca7224051d9e55adbd6d))
* **organizations:** add organizations CLI commands ([#68774](https://github.com/Arize-ai/arize/issues/68774)) ([179b1de](https://github.com/Arize-ai/arize/commit/179b1de72ddf4326cea85d883809c21b2c9c4417)), closes [#66090](https://github.com/Arize-ai/arize/issues/66090)
* **resource-restrictions-and-role-bindings:** add resource-restrictions and role-bindings commands ([#68633](https://github.com/Arize-ai/arize/issues/68633)) ([ebaa13b](https://github.com/Arize-ai/arize/commit/ebaa13b6714db9e98895c15ccaba8ba17f1804ef))
* **roles:** add roles CRUD commands ([#67233](https://github.com/Arize-ai/arize/issues/67233)) ([a88d94c](https://github.com/Arize-ai/arize/commit/a88d94ca625fba97cff528bd2fdecec7a01534ba)), closes [#66234](https://github.com/Arize-ai/arize/issues/66234)
* show API key hint during profile create ([#68884](https://github.com/Arize-ai/arize/issues/68884)) ([5036b1d](https://github.com/Arize-ai/arize/commit/5036b1da6fe1fadbca71a1bdfb59ee95e6744978))


### 🐛 Bug Fixes

* --space flag gaps (experiments create + api-keys) ([#68887](https://github.com/Arize-ai/arize/issues/68887)) ([d8dcd39](https://github.com/Arize-ai/arize/commit/d8dcd39b37b57163e6daeb9854355c667bef06e9))

## [0.13.0](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.12.0...arize-ax-cli/v0.13.0) (2026-04-16)


### 🎁 New Features

* **cli:** add `spaces delete` command with confirmation prompt ([#68721](https://github.com/Arize-ai/arize/issues/68721)) ([d36f5b0](https://github.com/Arize-ai/arize/commit/d36f5b05ef879f717e2b57d055491e20ff1686a3))

## [0.12.0](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.11.0...arize-ax-cli/v0.12.0) (2026-04-07)


### 🎁 New Features

* **cli:** add --single-host and --single-port flags for on-prem deployments ([#68107](https://github.com/Arize-ai/arize/issues/68107)) ([24252b2](https://github.com/Arize-ai/arize/commit/24252b2ef2c56a8b0d5e850675e1b39fc95476a4))

## [0.11.0](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.10.0...arize-ax-cli/v0.11.0) (2026-04-05)


### 🎁 New Features

* **annotation-queues:** add annotation-queues command group ([#67516](https://github.com/Arize-ai/arize/issues/67516)) ([24147d5](https://github.com/Arize-ai/arize/commit/24147d5a482d6806f5dd7a07bd83a84bbb8511a6))

## [0.10.0](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.9.1...arize-ax-cli/v0.10.0) (2026-04-02)


### 🎁 New Features

* add --name filter to list commands ([#67517](https://github.com/Arize-ai/arize/issues/67517)) ([27be0b4](https://github.com/Arize-ai/arize/commit/27be0b4ccdc076e54e006319d888133bd7c87dd5))

## [0.9.1](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.9.0...arize-ax-cli/v0.9.1) (2026-03-31)


### ❔ Miscellaneous Chores

* Pin specific version of the SDK, to avoid breaking changes ([#67405](https://github.com/Arize-ai/arize/issues/67405)) ([dc90d0f](https://github.com/Arize-ai/arize/commit/dc90d0f63c90e6464b92eed803c6794959e125d6))

## [0.9.0](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.8.0...arize-ax-cli/v0.9.0) (2026-03-30)


### 🎁 New Features

* **General:** support name-or-ID lookup for get/update/delete commands ([#67198](https://github.com/Arize-ai/arize/issues/67198)) ([85e7a76](https://github.com/Arize-ai/arize/commit/85e7a763c208728f367515140bafe1382aa9b57c))
* **General:** rename --space-id to --space and --project-id to --project ([#66726](https://github.com/Arize-ai/arize/issues/66726)) ([3791ce7](https://github.com/Arize-ai/arize/commit/3791ce738e77ee3f500e6b62bce73efac719ca74))
* **skills:** Add agent skills install ([#65808](https://github.com/Arize-ai/arize/issues/65808)) ([1b04b2c](https://github.com/Arize-ai/arize/commit/1b04b2ce9eada229443145111c691b5177834535)), closes [#65807](https://github.com/Arize-ai/arize/issues/65807)


### 📚 Documentation

* **cli:** use positional profile name in profiles commands and add force delete option ([#66493](https://github.com/Arize-ai/arize/issues/66493)) ([2f1befc](https://github.com/Arize-ai/arize/commit/2f1befccc5e79393e3055e7cfdb787b4af397881))

## [0.8.0](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.7.1...arize-ax-cli/v0.8.0) (2026-03-23)


### 🎁 New Features

* add stdin pipe support for datasets create/append and experiments create ([#66422](https://github.com/Arize-ai/arize/issues/66422)) ([3313e80](https://github.com/Arize-ai/arize/commit/3313e80eeaf391c6818d0d24dc3bae95eae07f3c))


### 🐛 Bug Fixes

* CLI tasks improvements ([#66412](https://github.com/Arize-ai/arize/issues/66412)) ([f58b5f3](https://github.com/Arize-ai/arize/commit/f58b5f3d052cac66eaa0f615f553cbb225bb8925))


### ❔ Miscellaneous Chores

* CLI general DX improvements ([#66413](https://github.com/Arize-ai/arize/issues/66413)) ([87e1391](https://github.com/Arize-ai/arize/commit/87e1391b27009290f78a3487ebd63d638f1f65a0))

## [0.7.1](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.7.0...arize-ax-cli/v0.7.1) (2026-03-23)


### 🐛 Bug Fixes

* Adding Missing Config Options (Classification choices, direction, data granularity) for Evaluators CLI ([#66401](https://github.com/Arize-ai/arize/issues/66401)) ([174eddb](https://github.com/Arize-ai/arize/commit/174eddb71056a4dc65e9e0e7d254a1ff3610facb))

## [0.7.0](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.6.0...arize-ax-cli/v0.7.0) (2026-03-21)


### 🎁 New Features

* **tasks:** implement evaluation tasks commands ([#66363](https://github.com/Arize-ai/arize/issues/66363)) ([49d04d9](https://github.com/Arize-ai/arize/commit/49d04d9478ccf3a60b3593f470cb62aa2abb82ef))

## [0.6.0](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.5.0...arize-ax-cli/v0.6.0) (2026-03-21)


### 🎁 New Features

* **ai-integrations:** add ax ai-integrations command group ([#65932](https://github.com/Arize-ai/arize/issues/65932)) ([e694a30](https://github.com/Arize-ai/arize/commit/e694a3029eb1dbc0d7d57f5803ab3ddf6ae2708e))
* **api-keys:** add ax api-keys command group ([#65931](https://github.com/Arize-ai/arize/issues/65931)) ([16178e2](https://github.com/Arize-ai/arize/commit/16178e2904c6e86e705eb22692f1a2d24dd78141))
* **cli:** auto-discover and register all command groups dynamically ([#66184](https://github.com/Arize-ai/arize/issues/66184)) ([772ef7c](https://github.com/Arize-ai/arize/commit/772ef7c2e574d88127bf797d44bc2422d767b913))
* **evaluators:** add evaluators command group ([#66096](https://github.com/Arize-ai/arize/issues/66096)) ([a0ce2ee](https://github.com/Arize-ai/arize/commit/a0ce2ee7671632bc6ab679f290fd08165258e788))
* **profiles:** add non-interactive config creation via TOML and CLI flags with precedence ([#65308](https://github.com/Arize-ai/arize/issues/65308)) ([c2444b7](https://github.com/Arize-ai/arize/commit/c2444b77b29997bc567b62f846bf18d24b0cc1e0))
* **prompts:** add ax prompts command group ([#65930](https://github.com/Arize-ai/arize/issues/65930)) ([206b678](https://github.com/Arize-ai/arize/commit/206b6784ff593b7ae34e0c8e04fd60b2c3a3b4af))


### 🐛 Bug Fixes

* add missing spinner feedback for resource fetching and deletion ([#66356](https://github.com/Arize-ai/arize/issues/66356)) ([b62df4b](https://github.com/Arize-ai/arize/commit/b62df4b1f418b5058f0c65f39bb7304f4870c60b))


### 💫 Code Refactoring

* **api-keys:** centralize ApiKeyStatus schema and update references ([#66333](https://github.com/Arize-ai/arize/issues/66333)) ([e32438d](https://github.com/Arize-ai/arize/commit/e32438d56098a25bd925c17ee262e0895e9f5ab6))

## [0.5.0](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.4.0...arize-ax-cli/v0.5.0) (2026-03-19)


### 🎁 New Features

* Add commands for evaluators ([#65528](https://github.com/Arize-ai/arize/issues/65528)) ([66b9113](https://github.com/Arize-ai/arize/commit/66b91135eb6cf76c840b2afe2362955b77c19d66))

## [0.4.0](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.3.0...arize-ax-cli/v0.4.0) (2026-03-17)


### 🎁 New Features

* **profile:** make profile loading resilient to invalid/extra config fields ([#65818](https://github.com/Arize-ai/arize/issues/65818)) ([e07f658](https://github.com/Arize-ai/arize/commit/e07f6585b7801c9f9a42d10f6c339e8c4d0c2b4e))
* **spaces:** Spaces CLI CRUD ([#64776](https://github.com/Arize-ai/arize/issues/64776)) ([54e3edf](https://github.com/Arize-ai/arize/commit/54e3edf42b6c2fbb438fba3dab7d7ec62c0b9f40))


### 🐛 Bug Fixes

* **cli:** add missing else so --verbose enables debug logging ([#65167](https://github.com/Arize-ai/arize/issues/65167)) ([ece74c9](https://github.com/Arize-ai/arize/commit/ece74c906d5611e0ebfc8f857d74fb53cfe2c4cf))
* **api-keys:** rename regenerate endpoint to refresh ([#65562](https://github.com/Arize-ai/arize/issues/65562)) ([36df84f](https://github.com/Arize-ai/arize/commit/36df84ff50fc77d121173cb449b49344e9b9dded))
* **cli:** unify output_file success messages in OutputFormatter ([#65279](https://github.com/Arize-ai/arize/issues/65279)) ([620a50a](https://github.com/Arize-ai/arize/commit/620a50a6000c62dd920aa80e5da420cad9be058f))


### ❔ Miscellaneous Chores

* Add AGENTS.md for SDKs and CLI ([#65353](https://github.com/Arize-ai/arize/issues/65353)) ([ab80512](https://github.com/Arize-ai/arize/commit/ab80512f26e3b2d08cca6fcc9c831f1b633e55d3))
* **ax-cli:** replace unrelated name with "project ID" in docs and tests    ([#65166](https://github.com/Arize-ai/arize/issues/65166)) ([61d96f3](https://github.com/Arize-ai/arize/commit/61d96f3656699cb95e52d61611b2f6bc8dd3d662))

## [0.3.0](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.2.1...arize-ax-cli/v0.3.0) (2026-03-09)


### 🎁 New Features

* A export commands and datasets append ([#64756](https://github.com/Arize-ai/arize/issues/64756)) ([45859e3](https://github.com/Arize-ai/arize/commit/45859e3f6f0338dbe3a8f4f9359a5978454175a3))
* Annotation Configs CRUD ([#64587](https://github.com/Arize-ai/arize/issues/64587)) ([3eafb99](https://github.com/Arize-ai/arize/commit/3eafb9986340154d5a36c16a3e3adca21c84530e))


### 📚 Documentation

* clean up CLI documentation ([#64762](https://github.com/Arize-ai/arize/issues/64762)) ([aeff0a0](https://github.com/Arize-ai/arize/commit/aeff0a070de85abc469f480ddeef5e5df82e4e1c))

## [0.2.1](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.2.0...arize-ax-cli/v0.2.1) (2026-03-04)


### ❔ Miscellaneous Chores

* Clean up changelog ([#64606](https://github.com/Arize-ai/arize/issues/64606)) ([05db1bf](https://github.com/Arize-ai/arize/commit/05db1bf9a6b1e66d410a1093cdf1b34bfe304f20))

## [0.2.0](https://github.com/Arize-ai/arize/compare/arize-ax-cli/v0.1.2...arize-ax-cli/v0.2.0) (2026-03-04)


### 🎁 New Features

* Add experiments commands ([#64260](https://github.com/Arize-ai/arize/issues/64260)) ([be2b732](https://github.com/Arize-ai/arize/commit/be2b7323367b9cf8898b30a05e960d4d3d56c753))


### 📚 Documentation

* README updates for spans and traces ([#64555](https://github.com/Arize-ai/arize/issues/64555)) ([865e7e6](https://github.com/Arize-ai/arize/commit/865e7e6eece1c756e5073086b38ba37b0fe0d48f))
* Small readme update ([#64590](https://github.com/Arize-ai/arize/issues/64590)) ([bddb598](https://github.com/Arize-ai/arize/commit/bddb598ca81379ed807f60733e7e5efe342ac44d))
