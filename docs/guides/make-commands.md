<!-- AUTO-GENERATED FILE — regenerate through `make gen` from the workspace root. -->
<!-- Source of truth: `<workspace-root>/docs/guides/make-commands.md`; adjust that workspace source, never this member projection. -->

# flext-infra - FLEXT Make Commands

> Project profile: `flext-infra`

<!-- TOC START -->

- [Discover commands](#discover-commands)
- [Canonical workflow](#canonical-workflow)
- [Codemod rule fixtures](#codemod-rule-fixtures)
- [Verb single-pass contract](#verb-single-pass-contract)
- [Information-preserving repair](#information-preserving-repair)
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

The consecutive generation passes prove the fixed point after structural rewrites.
`make build` packages the validated candidate; it does not replace runtime verification.
Each verb executes its declared operation directly. No project, file, pattern, action,
phase, fix, or changed-only selector may be attached to a standard verb.

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

## Verb single-pass contract

Each mutating verb owns exactly one operation per tool, and `make check` is strictly
read-only — no verb repeats another verb's work across the canonical sequence
`make fix && make fmt && make check`:

| Gate / tool                       | `make check` (read-only)           | `make fmt` (formatters) | `make fix` (one mutation)                  |
| --------------------------------- | ---------------------------------- | ----------------------- | ------------------------------------------ |
| `lint` — ruff                     | read-only `ruff` verdict           | —                       | one `ruff` repair pass                     |
| `format` — ruff                   | — (mutating)                       | `ruff` format pass      | —                                          |
| `markdown` — rumdl                | `rumdl check`                      | —                       | `rumdl fmt`                                |
| `markdown-format` — prettier      | `prettier --check`                 | `prettier --write`      | —                                          |
| `markdown-code` — ruff (embedded) | format verdict on parseable blocks | —                       | one format pass, clean round-trips spliced |
| `canonical-alias`                 | read-only scan                     | —                       | declared import rewrite                    |
| `smells` — qlty                   | read-only scan                     | —                       | —                                          |

`make fmt` never runs a lint pass and `make fix` never formats: each operation runs once
per verb, residue found by a mutation is reported there and enforced only by
`make check`, and `make fix`/`make fmt` repeated on a green tree are no-ops.

## Information-preserving repair

`make fix` repairs code; it never deletes information. The lint repair runs
`ruff check --fix` with the `make.ruff.lint_fix` flags of `config/codegen.yaml`, which
apply Ruff's safe fixes only: the typed Make contract rejects `--unsafe-fixes`. Ruff's
unsafe T201 fix once deleted `print(..., file=sys.stderr)` from a consumer script and
turned its failures silent.

The fix-safety policy lives in `config/tooling.yaml` (`Infra.tooling.tools.ruff.lint`)
and `make gen` renders it into every generated `pyproject.toml`:

- `unfixable` names the rules whose fixes delete a diagnostic print, an assignment, a
  redefinition, a duplicated key, value or test case, or a version block. Ruff keeps
  reporting them and never rewrites them, including a direct or IDE Ruff run.
- `extend-safe-fixes` is the only channel that promotes an unsafe fix into `make fix`. A
  rule enters it with evidence that its fix preserves code, comments and diagnostics.

`make mod` rewires `print` diagnostics instead of deleting them. In `src/`, `tests/` and
`scripts/`, a module that binds the `flext_cli` facade has `print(x)`,
`print(x, file=sys.stderr)`, `print(x, file=sys.stdout)` and a literal `flush` rewritten
to `cli.display_text(x)` by the codemod rule `rewire-print-to-cli-display-text`. Every
other form stays a reported T201 finding for its author.

## Markdown quality pipeline

The markdown standard lives once in `flext-infra/config/tooling.yaml`
(`Infra.tooling.tools.markdown`) and is projected to every repository by `make gen`:

- `rumdl` is the linter (markdownlint-compatible `MD*` rules through the generated
  `.markdownlint.json` / `.markdownlintignore`); syntax findings inside embedded code
  belong to the flext-tests markdown validator, not to a second linter.
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

## Related guides

- Development
- Testing
- Getting started
