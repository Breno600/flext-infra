---
name: flext-law
description:
  Apply the FLEXT-only architecture, workspace, generation, import, and fleet delta over
  canonical global execution governance.
---

# FLEXT Law

## Composition

Architecture decisions are recorded under `docs/architecture/adr/`; the ADR records
there are the durable rationale this law enforces.

This repository is the sole owner of the skill named `flext-law`. AI Hub projects it but
does not author it. Generic conduct, lane safety, evidence, Make-command selection, and
completion gates remain owned by:

- `~/.agents/AGENTS.md`
- `~/.agents/skills/agent-wide/personal/make-check/SKILL.md`
- `~/.agents/skills/agent-wide/verification/verification-loop/SKILL.md`

Read those skills and root `AGENTS.md`; this file adds only FLEXT domain law.

## Architecture and imports

- Dependency direction is `flext-core <- consumers`. `flext-infra` owns build, conform,
  codegen, and policy; it is never a runtime dependency.
- Facades compose in strict order `c -> t -> p -> m -> u`, with operational
  `r/e/x/h/d/s`. Reverse imports are `TYPE_CHECKING`-only.
- The canonical responsibility map is: `c` constants, `t` type aliases, `p` dependency
  protocols, `m` Pydantic v2 data models, and `u` pure utilities. `settings` owns
  external inputs, `config` owns validated derivation, `base` owns reusable foundations,
  `services` owns use cases, `api` is the sole composition root, and `cli` is a thin
  transport adapter when the project declares a CLI. Do not create competing long-name
  or alias layers.
- Dependencies cross use-case boundaries through `p` protocols and are provided
  explicitly by `api`. A service may not construct infrastructure, read process-global
  configuration, or resolve a dependency by string, reflection, service locator, hidden
  singleton, or module global. A container owned by `flext-core` may wire the graph only
  at the composition root.
- Each package has one thin `api.py` MRO facade and one simple generated root
  `__init__.py` with automatic lazy public exports. Custom import routers, eager
  alternatives, compatibility aliases, and duplicate facades are forbidden.
- Service exposure follows the canonical short alias: `base.py` imports `s` from
  `flext_core`, the package root lazily re-exports `s`, and consumers use
  `from <namespace> import s`. Never rename it to `core_s` or substitute an alternative
  service-base import.
- Declaration layers are pure data. Behavior belongs in utilities, services, bases,
  facades, or CLI layers. Owned data crosses boundaries through typed Pydantic v2 models
  and project `t.*`/`p.*` contracts.

## Runtime and language floor

- Every first-party FLEXT source, test, example, script, template, and generated surface
  targets the exact Python floor declared by the workspace toolchain; the current FLEXT
  floor is Python 3.13 with Pydantic 2.
- Use precise annotations and the strongest native language features available at that
  floor. Downgrading syntax, importing compatibility typing layers, or weakening an
  owned type to `Any`, `object`, an unparameterized collection, or an unchecked mapping
  is forbidden.
- Runtime-floor changes start at the workspace toolchain and dependency SSOT, then
  update templates, generated config, static analyzers, tests, CI, build, and deployment
  as one atomic migration. Consumers never select a lower floor.

## Release, deployment, and activation

- Development produces one immutable, typed candidate through the workspace Make owner.
  Release identifies that candidate by version and digest; deploy associates it with one
  declared environment and configuration projection; activation atomically switches the
  runtime to that already-validated candidate. These stages are distinct and may not
  rebuild one another's input.
- `settings` reads deployment inputs, `config` validates and derives runtime
  configuration, `services` execute use cases, `api` wires dependencies, and `cli` only
  translates command input and propagates the first failure.
- Staging validates the exact artifact with the shipped public surface before
  activation. Runtime evidence must prove artifact digest, environment association,
  configuration identity, process or endpoint health, and rollback target. A successful
  build or test is not deployment evidence.

## Sources, generation, and commands

- `config/*.yaml`, typed settings, schemas, and generator policy are the SSOT. Change
  the owner, regenerate every projection, and remove the superseded implementation in
  the same cutover.
- Generated facets, root imports, managed `pyproject.toml` sections, Make surfaces, CI,
  and documentation are never hand-edited at consumers. Their canonical owner is
  `flext-infra` plus explicit `config/` overlays.
- Run setup, conform, codegen, docs, checks, tests, WAZA, and publication only through
  the active workspace root Make dispatcher. A missing or broken verb is repaired
  generically in `flext-infra`, then reused by workspace and standalone projects; it is
  never bypassed.
- Invoke the standard Make verbs directly. Mutating verbs mutate by default with zero
  variables; agents never add `WHAT=` or `PROJECT=` to setup, generation, repair,
  formatting, checking, or testing.
- Only `make upg` resolves newer dependencies and writes the committed `uv.lock`,
  `mise.lock`, and Mise runtime pin. `make setup` provisions the physical workspace
  environment from those frozen inputs. Generation and runtime verbs neither install
  nor upgrade dependencies. Correct the canonical generator when this lifecycle fails;
  never install or resolve packages manually to make the next gate pass.
- Adopt concurrent work by fix-forward. Fetch each repository's integration tip, absorb
  it with `git merge --no-ff`, and preserve all compatible work. Publish through that
  integration branch and measure the remote merge SHA; a local merge or an old gate
  receipt never proves integrated runtime.
- Structural rewires run through `make mod`. Its canonical FLEXT engine composes
  `ast-grep` rewrites, Rope semantic refactors, and real `pyright-langserver`
  diagnostics before the fixed point is accepted. Repetitive manual call-site editing is
  prohibited; change the codemod or its typed automation owner and let that pipeline
  propagate the cutover.
- Symbol placement and nesting are discovered from the live typed module path, AST/Rope
  identities, and LSP references. Hand-maintained symbol/class mapping catalogs, copied
  path registries, inert entries, and review-only confidence lists are forbidden;
  ambiguity fails at the discovery owner instead of selecting a fallback. The reusable
  classifier or planner survives only on the appropriate public `c/t/p/m/u` facade.
- Git repositories and local Git operations belong to `flext-infra`. GitHub and CRG
  belong to ai-hub. When ai-hub publishes commands, hooks, MCP routes, or `ai-hub-*`
  daemons, FLEXT may consume those public runtime protocols as optional enrichment; it
  never imports ai-hub or CRG as a library. An absent optional host runtime is not a
  FLEXT error. Once an available integration is selected, its first failure remains
  visible and is never normalized.
- A detection-only AST finding keeps the final gate red but never blocks safe actionable
  rewrites in the same `make mod` invocation. Apply the mechanical cut, perform the
  semantic rewire, delete the superseded owner, and repeat until both classes are zero.
  Never stop before apply merely because a later semantic finding still requires repair.
- Long native phases emit causal progress at intervals below 60 seconds. Piping through
  `tail`, truncating/capping output, quiet flags, warning filters, and wrappers that
  hide the first traceback are forbidden evidence paths.
- `flext-tests` owns reusable fixtures and behavior helpers. Packages consume them
  through public facades rather than creating local copies.
- FLEXT tests exercise only public facades and observable runtime behavior. They use
  `tm`, canonical `c/t/p/m/u` contracts, the unified `conftest.py`, and typed shared
  fixtures instead of mocks, internal assertions, copied setup, or hardcoded
  project-owned values. Every test run retains the canonical testmon cache, including an
  explicitly requested full run.

## Fleet boundary

- First-party FLEXT members and standalone repositories consume the same branch-matched
  law, Make control plane, and generated conventions.
- Third-party forks and content-only repositories are not FLEXT members: do not impose
  FLEXT architecture, dependency injection, typing modernization, language features,
  lint, generation, or package layout on them. Follow the upstream architecture, style,
  runtime floor, toolchain, build, release, and deployment protocol. Local governance is
  limited to typed provenance, association, credentials, artifact identity, environment
  ownership, and runtime verification metadata in a bounded `config/` overlay.
- Workspace and standalone CI are generated once by `flext-infra conform`. Exceptions
  are configuration overlays, never duplicate pipelines or custom implementations.
- Historical branches, archives, generated outputs, and other worktrees are evidence
  only. The active branch-matched canonical sources define behavior.

## Recovering namespace and runtime work

- Start from the repository's maintained execution handoff and ADR index before
  rescanning the fleet. In flext-infra, `docs/guides/execution-context.md` points to the
  current namespace/runtime handoff, its plan, measured revision and canonical Beads.
  Resolve an absent ADR at its documented owner; do not invent a missing record or load
  a parent runtime to compensate for missing context.
- Compare namespace, codemod and runtime-census inventories by the contracts they
  actually inspect. Zero codemod findings alone never proves namespace conformance or
  working runtime. Record which transformations execute and which findings remain before
  expanding a batch.
- Preserve mutability, inheritance, expression dependencies and consumer imports through
  the public transformation. Test-name preservation after a merge is only an inventory
  check; execute the public runtime and collection before claiming the combined code
  works.
- Keep operator-approved acceptance exceptions attached to that execution's handoff and
  Beads. A limited check acceptance does not change the fleet law, suppress a diagnostic
  or close the remaining architecture defects.
