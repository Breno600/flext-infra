<!-- AUTO-GENERATED FILE — regenerate through `make gen` from the workspace root. -->
<!-- Source of truth: `<workspace-root>/docs/guides/make-commands.md`; adjust that workspace source, never this member projection. -->

# flext-infra - FLEXT Make Commands

> Project profile: `flext-infra`

<!-- TOC START -->

- [Discover commands](#discover-commands)
- [Canonical workflow](#canonical-workflow)
- [Codemod rule fixtures](#codemod-rule-fixtures)
- [Verb single-pass contract](#verb-single-pass-contract)
- [Repair selector verbs and the mod loop](#repair-selector-verbs-and-the-mod-loop)
- [Fleet automation verbs](#fleet-automation-verbs)
- [Mandatory unsafe repair channel (operator law 2026-10-05)](#mandatory-unsafe-repair-channel-operator-law-2026-10-05)
- [Markdown quality pipeline](#markdown-quality-pipeline)
- [Test contract](#test-contract)
- [Failure contract](#failure-contract)
- [Scope and generation](#scope-and-generation)
- [Related guides](#related-guides)

<!-- TOC END -->

`make help` at the workspace root is the executable authority for command grammar. This
guide records the invariants that every declared verb must keep.

## Discover commands

```bash
make setup
make help
```

Never infer a target, flag, or selector from historical documentation. When a required
verb is missing or broken, repair the root dispatcher owner and rerun that verb.

## Canonical workflow

Use the standard verbs directly from the workspace root:

```bash
make setup
make gen
make mod
make gen
make gen
make fix
make fmt
make check
make test
make build
```

The consecutive generation passes prove the fixed point after structural rewrites. The
first pass derives Ruff source roots from the declared template outputs, including test
directories it will create, so the verification pass sees the same topology.
`make build` packages the validated candidate; it does not replace runtime verification.
Each verb executes its declared operation directly. No project, file, pattern, action,
phase, fix, or changed-only selector may be attached to a standard verb. When
`make setup` initializes an absent governed submodule, it uses the explicit GitHub
credential selected by the root Make contract in a Git credential helper scoped to that
invocation. The token stays in the process environment, outside command arguments and
logs. `make.submodule_timeout_seconds` in `config/codegen.yaml` bounds the clone.
Provisioning uses `git submodule update --init --depth 1`, the same depth
private submodule init uses, because setup only needs the recorded gitlink
and a full history of a large object database cannot finish inside that
deadline. A timed-out or incomplete checkout fails the verb. Existing
submodule worktrees are validated without fetching or rewriting them.

`make help` is the complete live inventory. Additional declared verbs such as `upg`,
`docs`, `audit`, `status`, `waza`, `duplication`, and the release verbs retain their own
single operation and are invoked only when their scope applies. The `docs` lifecycle
ends with an audit: any finding fails the verb and remains in
`.reports/docs/audit-report.md`. Command guidance is checked in executable shell blocks
and inline instructions; descriptions of internal tools are not shell guidance.

## Codemod rule fixtures

Every ast-grep rule has a test (`<rule-id>-test.yml` with `valid` and `invalid` cases)
and, for each invalid case, a committed snapshot of what the rule reports and rewrites.
`make mod` verifies them with `ast-grep test` and never rewrites a snapshot: a changed
fix output, a missing snapshot, or a snapshot of a removed rule or deleted test case
fails the verb instead of being accepted as the new expectation.

`make mod-snapshots` is the one explicit regeneration. It rebuilds the snapshots of the
rules this repository owns from their tests, prints every created, updated or removed
snapshot, and leaves the diff for review in the same commit as the rule change.
Inherited rule providers keep the snapshots their owner ships.

For private imports, `make mod` first resolves whether the importing file and target
module share an owner. Same-owner imports become relative imports without inspecting an
installed package with the same top-level name. Only cross-owner imports require
installed public-facade discovery; invalid relative imports in that dependency remain
errors.

## Verb single-pass contract

Each mutating verb owns exactly one operation per tool, and `make check` is strictly
read-only — no verb repeats another verb's work across the canonical sequence
`make fix && make fmt && make check`:

| Gate / tool                       | `make check` (read-only)           | `make fmt` (formatters) | `make fix` (one mutation)                  |
| --------------------------------- | ---------------------------------- | ----------------------- | ------------------------------------------ |
| `lint` — ruff                     | read-only `ruff` verdict           | —                       | one `ruff` repair pass                     |
| `format` — ruff                   | — (mutating)                       | `ruff` format pass      | —                                          |
| `markdown` — rumdl                | `rumdl check`                      | —                       | `rumdl check --fix`                        |
| `markdown-format` — prettier      | `prettier --check`                 | `prettier --write`      | —                                          |
| `markdown-code` — ruff (embedded) | format verdict on parseable blocks | —                       | one format pass, clean round-trips spliced |
| `smells` — qlty                   | read-only scan                     | —                       | —                                          |

`make fmt` never runs a lint pass and `make fix` never runs the format-only gates: each
operation runs once per verb. `rumdl check --fix` repairs fixable findings and returns
a failing status for residual findings. A mutation that cannot complete its declared
repair stays red before `make check`; on a green tree, repeated `make fix` and
`make fmt` are no-ops.

## Repair selector verbs and the mod loop

`make fix-namespace` and `make fix-accessors` are repair selectors over the same
engines `make mod` invokes as callback phases of its joint fixed point:

- `fix-namespace` runs the rule catalog's relocation cascade (protocol,
  typing-alias, future-annotations, module-import, package-root-import,
  own-package-import, facade-class) once per project and rescans for the
  residue; `make mod` runs the identical cascade between its semantic and
  text phases.
- `fix-accessors` rewrites accessor names whose defining module resolves
  (through Rope) inside the rename catalog's origin package; a homonym owned
  by the scanned repository or another library is skipped with a warning, and
  `make mod` applies the identical origin-aware rewrite as a callback phase.
- Both verbs default to dry-run on the documented CLI (`refactor
namespace-enforce` / `refactor accessor-migrate` without `--apply` reports
  without writing) and publish their structured receipts under
  `.reports/refactor/`; a second run over a converged tree writes nothing.

## Fleet automation verbs

Two surfaces compose the per-repository verbs into fleet-scale loops. Both are
`flext-infra` CLI subcommands and publish one structured receipt per run.

- `flext-infra workspace fleet-gaps` walks the invoking workspace's declared
  members and external consumers and publishes `.reports/fleet-gaps.json`:
  per repository, its porcelain dirty paths, its open pull requests (a
  failing `gh` degrades to an empty list), its local branches not merged into
   the integration line, explicitly selected lint/Pyrefly execution counts,
   the codemod count its own `.reports` carries (an absent mod artifact counts
   zero), and the standards
  presence columns (`AGENTS.md`, `.agents/skills/.flext-stamp.json` with its
  `distribution_version`, `.beads/config.yaml`). The report carries no
   timestamp: an unchanged tree re-publishes a byte-identical receipt.
   `--quality-receipts path/to/check-report.sarif[,other/check-report.sarif]`
   selects exact published check invocations, with relative paths resolved from
   `--repository-root`. Their typed SARIF properties bind execution verdicts to
   canonical project roots. No selection, missing gates, unreached projects and
   file-scoped checks yield `null` (unknown/not executed), not zero or PASS.
   Missing/malformed selected receipts, unrelated roots, native tool errors,
   missing native output and duplicate full-project repo/gate selections fail
   before hygiene probes. The auditor never searches by time or combines counts
   from multiple captures of the same repo/gate.
- `flext-infra refactor violations-sweep` measures the repository's mod scan
  totals, runs the canonical repair sequence (`make fix`, `make fmt`,
  `make mod`) in order, measures again, and publishes
  `.reports/refactor/violations-sweep.json`. The command FAILS the moment any
  total increased: automation may reduce a tree's violations, never grow
  them. A sweep over a tree the repair sequence cannot improve is a
  zero-delta success.

## Mandatory unsafe repair channel (operator law 2026-10-05)

**`make fix` ALWAYS runs `ruff check --fix --unsafe-fixes --preview`. This is a direct
operator order: the unsafe-fix channel is OBLIGATORY in every project and subproject,
forever, and must never be disabled again.** The typed Make contract enforces it:
`MakeRuffSpec` fails validation when `make.ruff.lint_fix` lacks `--unsafe-fixes`, so a
configuration that disables the channel cannot even generate. Removing the flag is a
regression against an explicit operator order and is reverted on sight.

The fix-safety policy lives in `config/tooling.yaml` (`Infra.tooling.tools.ruff.lint`)
and `make gen` renders it into every generated `pyproject.toml`:

- `unfixable` names the rules whose fixes delete a diagnostic print, an assignment, a
  redefinition, a duplicated key, value or test case, or a version block. Ruff keeps
  reporting them and never rewrites them, including a direct or IDE Ruff run. This is
  rule selection — it protects specific destructive fixes and never disables the
  mandatory unsafe channel.
- `extend-safe-fixes` keeps its historical evidence records from the opt-in era; the
  channel itself no longer needs promotion because it is always on.

`make mod` rewires `print` diagnostics instead of deleting them. In `src/`, `tests/` and
`scripts/`, a module that binds the `flext_cli` facade has `print(x)`,
`print(x, file=sys.stderr)`, `print(x, file=sys.stdout)` and a literal `flush` rewritten
to `cli.display_text(x)` by the codemod rule `rewire-print-to-cli-display-text`. Every
other form stays a reported T201 finding for its author.

## Native type descriptor policy

Operator approval on 2026-10-09, **"Parametrizar Dois Descritores"**, authorizes only
`__base__` and `__bases__` through
`Infra.tooling.tools.ruff.lint.pylint.allow-dunder-method-names` in
`config/tooling.yaml`. The typed model rejects unrelated names; generation and Ruff
conformance derive the managed `tool.ruff.lint.pylint` table from that owner.

Python documents [`type.__base__`][python-type-base] as the single base responsible for
instance memory layout and [`type.__bases__`][python-type-bases] as the tuple of direct
bases. Protocols retain read-only properties, their signatures, and native identity.
[Ruff PLW3201][ruff-dunder] supports this exact setting: the rule remains enabled for
other unrecognized dunders, without `noqa`, per-file ignores, or rule disabling.

[python-type-base]: https://docs.python.org/3.13/reference/datamodel.html#type.__base__
[python-type-bases]: https://docs.python.org/3.13/reference/datamodel.html#type.__bases__
[ruff-dunder]: https://docs.astral.sh/ruff/rules/bad-dunder-method-name/

## Markdown quality pipeline

The markdown standard lives once in `flext-infra/config/tooling.yaml`
(`Infra.tooling.tools.markdown`) and is projected to every repository by `make gen`:

- `rumdl` is the linter (markdownlint-compatible `MD*` rules through the generated
  `.markdownlint.json` / `.markdownlintignore`); syntax findings inside embedded code
  belong to the flext-tests markdown validator, not to a second linter. Its fix pass
  keeps unfixable findings visible and makes `make fix` fail when they remain. MD013
  uses standard reflow to wrap overlong prose; paragraph-normalization mode is not
  selected because its separate hint cannot be resolved by the native writer.
- `prettier` (pinned 3.5.x — newer releases dropped prose reflow) is the formatter:
  `prettier --check` in `make check`, `prettier --write` in `make fmt`.
- `markdown-code` holds parseable embedded Python and doctest examples to the
  ruff-format contract; unparseable documentation fragments are prose and stay with the
  validator. Generated and provider-projected trees (`.agents`, `.claude`, `.gemini`,
  `AGENTS.md`, `target/`, and friends) are excluded by the same SSOT list.

## Test contract

`make test` runs the incremental selection. `make test-full` first runs that operation,
then the complete suite, including configured external and CI-excluded markers. The
runner owns this sequence, one monotonic deadline, and the same persistent Testmon
database, located by the flext-infra generated configuration. External tests keep their
declared runtime and authentication requirements. Direct runner commands and
cache-clearing bypasses are prohibited.

Separate receipts preserve each phase's mode, raw result, inventory, execution, and
deselection counts. Warnings are counted per subprocess and globally, including any
explicitly suspended MRO warnings. Only a typed incremental cache hit with database
integrity checks and complete deselection accounting may execute zero tests; it is never
reported as tests passed. The full phase must execute its complete nonempty inventory.

## Failure contract

- The first exception, traceback, and non-zero exit propagate unchanged.
- Warnings, skips, empty output, and missing tools are failures.
- No retry, fallback, suppression, normalization, partial run, or alternate raw tool
  path can replace the canonical verb.

## Scope and generation

The root dispatcher resolves workspace scope from its typed topology. Generated Make
surfaces and documentation are changed at their template or configuration owner, then
regenerated with `make gen`.

When conformance selects multiple repositories, lazy initializer planning opens each
repository in its own Rope workspace. Conformance combines their authenticated file
plans into one transaction receipt and verifies the selected publications together.

## Related guides

- Development
- Testing
- Getting started
