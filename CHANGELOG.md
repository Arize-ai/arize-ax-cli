# Changelog

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
