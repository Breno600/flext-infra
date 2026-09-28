# Release v0.12.0

<!-- TOC START -->

- [Scope](#scope)
- [Projects impacted](#projects-impacted)
- [Pull requests since last release](#pull-requests-since-last-release)
- [Current state](#current-state)

<!-- TOC END -->

## Scope

- Release version: 0.12.0
- Projects packaged: 2

## Projects impacted

- root
- flext-infra

## Pull requests since last release

- Initial tagged release

## Current state

Release notes are maintained history; this section records the live state of the
`0.12.0-dev` line without rewriting shipped history.

- **Integration tip:** `flext-infra@a2bd0a7262a0eab84bd7e4c27f8bdd10de0d247a`,
  superproject `676ae7aa3c7511ce3b133fdd31e43cfc49e7564f`.
- **Not green:** `make setup`, `make gen`, `make check`, `make test`, `make build` have
  no current passing evidence on this tip. The canonical cycle (phases 3 and 8 of the
  runtime-modernization plan) is not started.
- **Open defects:** `_lazy_analysis` scope mismatch in
  `src/flext_infra/codegen/_conform/execute.py:376/598`; god modules `_models/config.py`
  (3.342 LOC) and `codegen/conform.py` (2.996 LOC) unchanged.
- **Adopted constraints:** `APPLY`, `uv.lock`, `mise.lock` and `exclude-newer` are
  banned project-wide; Beads are Gas City only; `make setup` is the sole provisioning
  path.
- **Recovery:** Gas City tasks `flext-itpd1.2` and `flext-5fxu6.4`, plus
  `docs/roadmap/namespace-automation-handoff-2026-09-14.md`.
