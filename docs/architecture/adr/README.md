# Decision map for flext-infra

<!-- TOC START -->

- [Known divergences](#known-divergences)
- [Current contract](#current-contract)

<!-- TOC END -->

This index points to the architectural owners that govern flext-infra. The platform
ADRs below belong to the `flext` workspace; this repository keeps the code, its tests,
and this navigation map. The index does not replace or duplicate the decision text.

| Reference                                                                                                                                  | Responsibility                                            | Application in flext-infra                                                                 |
| ------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| [ADR-005](https://github.com/flext-sh/flext/blob/0.12.0-dev/docs/architecture/adr/005-config-settings-constants-templates-schemas-ssot.md) | Configuration, settings, constants, templates and schemas | Use §§1–2 for configuration and its typed owners; fix templates/SSOT before projections    |
| [ADR-010](https://github.com/flext-sh/flext/blob/0.12.0-dev/docs/architecture/adr/010-unified-project-standardization-via-codegen.md)      | Standardization and semantic discovery                    | §3b describes source discovery and automatic rewiring; check it against the implementation |
| [ADR-014](https://github.com/flext-sh/flext/blob/0.12.0-dev/docs/architecture/adr/014-family-part-shape-rope-codemod-rules.md)             | Family shape and Rope codemods                            | Align orphans, wrappers, consumers and namespace detection                                 |

## Known divergences

These divergences remain open in the platform ADR text. Do not resolve them silently;
report a conflict to the owning ADR instead.

- ADR-012 is absent from this directory. The configuration reference is ADR-005 §§1–2
  together with the `_settings.py` and `_config.py` docstrings.
- ADR-005 §6 carries a historical AST prohibition, while ADR-010 §3b describes the
  AST/Rope/LSP pipeline the code implements.
- ADR-010 §2 mentions Make verbs with selectors, while the current Make surface uses
  selector-free verbs and no longer has `APPLY`.

## Current contract

The current implementation supersedes the divergent ADR text on these points:

- `APPLY` is removed from every producer and consumer.
- Configuration declares `latest`. Only `make upg` resolves newer releases and writes
  the committed `uv.lock` and `mise.lock`; `make setup`, `make gen` and `make fmt`
  install frozen from those locks.
- Mise manages itself through the `[tools]` entry `mise.lock` pins. The fleet toolchain
  has no npm-backed tool; `make setup` installs only the declared tools and proves each
  one is the self-contained locked release (platform ADR-025).

The [execution context guide](../../guides/execution-context.md) documents the
operational details.
