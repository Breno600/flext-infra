# Execution context

<!-- TOC START -->

- [Runtime is the authority](#runtime-is-the-authority)
- [Environment activation](#environment-activation)
- [Dependency locks](#dependency-locks)
- [Runtime environment](#runtime-environment)
- [Mise toolchain](#mise-toolchain)
- [SonarCloud exclusions](#sonarcloud-exclusions)
- [Bootstrap credentials](#bootstrap-credentials)
- [Evidence and checkpoints](#evidence-and-checkpoints)
- [Check gate partitions](#check-gate-partitions)
- [Bounded Mypy failure status](#bounded-mypy-failure-status)
- [Abstraction-boundary project identity](#abstraction-boundary-project-identity)
- [Codemod scanner contract](#codemod-scanner-contract)

<!-- TOC END -->

## Runtime is the authority

Correct runtime behavior defines the contract; tests verify it. Replace mocks, fake
tools, private-function access, and assertions that only check how code was written
with observable inputs and effects through public interfaces, preserving functional
coverage. First reproduce the real public path and identify the executed artifact. Fix
obsolete tests or fixtures after that proof, never by changing the environment to keep
their expectations. A test result alone does not certify setup, generation, or
consumption at the integrated revision.

Before repeating a broad search, confirm branch, HEAD, local changes, PR, and declared
base. Check the runtime with `make status`: the execution path and installed version
must match the code under validation. An earlier log or an installation from a parent
workspace does not certify a standalone checkout. Work on the freshly fetched
integration tip of every repository involved.

## Environment activation

The `make setup` contract includes approving the `.envrc` with `direnv allow`.
Operational Make verbs activate that environment before handlers and hooks, except the
activation producer declared in `make.verbs`. For `gen`, the pin and the provisioned
physical environment are required before `pre-gen` and the selected handler. The default
handler runs one conform transaction, which includes generating the `.envrc`; a declared
`_custom-gen` still replaces that handler. Only then does Make activate the generated
environment and run `post-gen`. A producer or activation failure prevents the later hook
and keeps the command red, so `make gen` can repair a broken generated activation
without another writer outside the journal. Initial provisioning remains the
responsibility of `make setup`. Real commands work without wrapping each call in
`direnv exec`.

Activation exposes the native Mise shims and watches `.mise.toml` and `mise.lock`.
The installed release is selected by the self-management entry in that lock, not
by a separate launcher or pin file. Make and direnv restrict global and system
configuration discovery to the elected runtime's `.mise` directory; unrelated
host tool declarations never belong to project provisioning. A missing pin
requires `make upg`; missing installed tools require `make setup`, which
provisions before activation. Activation itself neither installs nor resolves.

When Beads tracking is configured, the generated `.envrc.local` carries its environment:
`AGENTS_GAS_CITY_ROOT` selects the Gas City root, the Gas City runtime publication
provides the port, and the rig metadata provides its database in `server` mode. The
`.envrc` loads that file last. The environment source declared in
`BeadsWorkspaceEnvironmentSpec.environment_sources` provides the city identity; the
template fixes neither its location nor a port. JSON reads must succeed before any
variable is exported. If generation drops the server selection, fix the model or
template and regenerate; never initialize an embedded database or write host and port
by hand.

## Dependency locks

Configuration declares `latest`. `make upg` is the only verb that resolves newer
releases and writes the committed `uv.lock` and `mise.lock`. `make setup` installs
from committed locks; `make gen` and `make fmt` neither install nor upgrade tools.
Git dependencies follow their declared integration branches, and `APPLY` stays removed.

One `make upg` run converges. It resolves the Mise lock before provisioning,
upgrades `uv.lock`, installs the upgraded generator and conforms dependency floors.
It runs generation's producer half, relocks the projected manifests, reinstalls
and verifies the resulting runtime before generation's activation half. A
requirement or Mise self-management release that only the upgraded generator
declares therefore reaches the lock and environment in the same run. The declared
lock platforms and release cooldown come from the typed toolchain; never edit
native lock payloads or substitute manual installation commands.

Each internal `flext-*` requirement declares its integration line in `pyproject.toml`,
never a commit: the resolved commit exists only in `uv.lock`, and only `make upg` moves
it to the line tip. The manifest does not pin revisions. A commit left in the
`pyproject.toml` projection is residue: `make gen` re-renders it on the detected line.
When the projection carries no line, a hand-written `project.flext_source` in the
manifest declares it, and a commit in a hand-written source fails. Fix the setup or
`upg` owner and regenerate through `make gen`; manual installs do not replace the cycle.

A workspace root declares local-member requirements as bare distribution names and
resolves them through `[tool.uv.sources]` entries with `workspace = true`. The root
alone owns `[tool.uv.workspace]`; member manifests never declare a nested workspace.
Publishable members retain their declared inline Git provenance and, while attached,
redirect local sibling requirements through their own workspace-source overlay.
Standalone conformance removes that overlay without removing the declared Git
requirements. Dependencies outside the declared workspace retain their governed
integration source rather than becoming local members.

## Runtime environment

Code in a checkout runs in the environment of its `RUNTIME_ROOT`. The generated Makefile
exports `RUNTIME_ROOT`, and flext-infra reads it as a typed declaration: the
`fresh-import` validation runs its probes with the platform-specific
Python interpreter in the derived `RUNTIME_VENV`, never
with the interpreter hosting the tool. Without a declaration, the owner derives the
checkout's Git root; a declaration without an interpreter fails.

The environment belongs to the `RUNTIME_ROOT`. A member attached as a submodule uses
its containing Git superproject's environment. A primary standalone checkout keeps
`<RUNTIME_ROOT>/.venv`. A linked Git worktree must use the sibling environment at
`<RUNTIME_ROOT>/../.venv>`.
The directory component is declared in `config/codegen.yaml`; Git's distinct worktree
and common directories identify the linked checkout. The generated Makefile, generated
`.envrc`, and `runtime_environment_dir` derive the same path. Neither a caller
variable nor a checkout-local symlink may redirect the environment.

## Mise toolchain

Mise manages itself: the generated `.mise.toml` declares the `toolchain.mise_selector`
release as a `[tools]` entry, and `mise.lock` pins it like every other tool. One host
Mise capable of reading the committed lock provisions that entry; setup verifies
the installed release and enters the recursive Make lifecycle through it. Every
later `mise` resolved through the shims is the pinned release, and
`_builtin_require_mise` fails when the running Mise differs from the lock.
Separate `mise.version`, bootstrap launchers and staged lock-convergence scripts
are not lifecycle owners.

`toolchain.tools` in `config/codegen.yaml` declares every fleet tool. Each comes from a
native, checksum-locked owner (aqua, GitHub releases, conda, or a Mise core backend);
the toolchain model rejects an `npm:` selector at load (ADR-025). A tool whose upstream
release metadata publishes no checksum declares `lock_checksum: false`.

`make setup` and `make upg` pass the explicit declared key list
(`toolchain.mise_install_keys`) to `mise install`. A bare `mise install` would also
provision every tool of the operator's global Mise registry, so no generated recipe
runs one. After the environment is provisioned, `make setup` runs the reality proof
(`flext-infra codegen mise-proof`) before `post-setup`. For each declared tool, in
order, it stops at the first defect:

1. the `mise.lock` entry exists, names a version the toolchain selector accepts, and
   carries a checksum for the current platform when `lock_checksum` requires one;
2. `mise where <key>@<version>` names the install root;
3. `mise which <binary>`, and every symlink hop it resolves through, stays inside that
   root;
4. the tool's declared `version_probe` reports the locked version.

The proof has no fallback, retry, or warning-only mode.

A project `bin/` never enters PATH (shell, `BASH_ENV`, or CI `GITHUB_PATH`): Mise binds
the shared shims to the first `mise` on PATH. Caches and installations stay out of Git.

Mise reaches GitHub to install a tool missing from its cache and to resolve
releases during `make upg`. Only `make upg` writes `mise.lock` and `uv.lock`;
`make setup` never writes either. A missing or incompatible Mise lock entry fails
with its original diagnostic and exit status, without disabling lockfiles or
retrying. Setup checks whether `uv.lock` agrees with the manifests. A matching lock uses
`--locked`; a drifted lock emits its diagnostic and installs the committed lock
with `--frozen`, without rewriting it. Drift and any resulting dependency
incompatibility remain red until `make upg` produces matching locks. A missing
lock fails with an actionable diagnostic. A failed native resolver or installer
retains its original failure; no downgrade, retry or disabled lock policy masks it.
Only successful resolution, installation and generation establish alignment.
The platforms declared by `toolchain.mise_lockfile_platforms` compose the lock
together with the platform of the machine running the upgrade, which Mise always
includes.

The default `make gen` handler passes explicit `--scope all` to conform at
`PROJECT_ROOT`: a workspace invocation covers its root and every declared member,
while a standalone repository has only itself. The request model's default remains
`SELF` for callers that do not select a scope, including file-only surfaces.
Generation owns one transaction for ordinary projections, Mise artifacts, lazy
exports and docs; no additional writer runs before or after its journal.
A planned deletion has no staged replacement, but its successful result still
carries a journal receipt: absence belongs inside the typed receipt, never in
`r.ok(None)`. Repeated unchanged generation must converge before publication.

## SonarCloud exclusions

The committed-lock contract also removes the former SonarCloud exclusion for a missing
lock. `codegen.sonarcloud.issue_exclusions` remains the single source of the server
configuration. With `SONAR_TOKEN` in the environment, `make sonarcloud-sync` sends a
non-empty list through the `settings/set` API; an empty list uses
[`settings/reset`](https://sonarcloud.io/web_api/api/settings/reset) with `component`
and `keys`. The command rereads `settings/values` and requires the exact effective
value, including inherited exclusions. If the reset reveals an exclusion from a higher
level, the divergence remains a failure.

## Bootstrap credentials

The GitHub credential is selected in the generated Makefile preamble, for every
Make entry: the first non-empty of the caller's `GITHUB_TOKEN`, `GH_TOKEN`,
`MISE_GITHUB_TOKEN`, then the existing `gh auth token` producer in the declared
local or unset CI context. Make exports that one value as `GITHUB_TOKEN`, `GH_TOKEN`,
and `MISE_GITHUB_TOKEN`, so gh, uv, and mise read the same credential and no inherited
alias can shadow it; `GITHUB_API_TOKEN` is unexported. Native Mise inherits those
exports. The generated Make and direnv owners isolate global/system configuration
discovery, not all process variables; other caller environment values remain
inherited. `status` reports the selected source, extraction exit status, credential
presence, and CI classification without printing the value or credential-command
stderr. Its initial entry reports the producer; a recursive entry can report the
normalized inherited `GITHUB_TOKEN` instead. Caller credentials report extraction
as `not-selected`, not as a successful credential-command invocation.

Optional credentials do not block offline verbs. In `setup` and `upg`, a selected
gh producer's failure is reported and its exit status propagated before the first
Mise lock or install; success with an empty credential also fails before provisioning.
CI classification and caller precedence are unchanged. An invalid supplied token
preserves the backend's native error, without an
anonymous retry or source switch. CI jobs inject `GITHUB_TOKEN`; containers receive
the variable or a BuildKit secret explicitly.

## Evidence and checkpoints

Each piece of evidence identifies command, directory, observed revision, exit code, and
decisive result. A run that is in progress, interrupted, or missing its exit code is not
green. Concurrent changes require a fresh read before writing and revalidation of the
affected paths. A published work-in-progress commit preserves work and enables review;
completion requires integration and runtime measured at the integrated SHA.

For namespace automation, investigate catalog, classifier, transformation, publication,
and consumers in that order. The namespace laws are codemod catalog rules, so the
codemod gate is their one verdict. Preserve mutability, inheritance, imports, and
collection; validate the transformation through the public interface before widening
the batch. Structural refactors go through `make mod`.

## Check gate partitions

`make file-gate FILE=<repository-relative path>` delegates to the existing
`check run --file` owner, never bare analyzers or a second gate engine. The raw
Make value travels through an exported environment value, not interpolated shell
source. Selection rejects empty, absolute, traversal, missing, non-Python and
symlink-component paths before creating reports or invoking tools. Only the literal
file reaches each gate's existing `check_files`; no mutation is permitted.
The Make pre-gate explicitly selects registered lint, format, Pyrefly, Mypy,
Pyright and codemod gates through the existing typed `RunCommand.gates` owner and
`resolve_gates`; no separate gate vocabulary or configuration is introduced.
The public `check run --file` requires explicit `--gates`, never silently falls
back to whole-project gates, and rejects unknown names before scanner execution.
Mypy and Pyright findings retain the existing informative SSOT policy; native
errors, missing tools/configuration and malformed reports remain blocking.
Codemod uses its elected, staged provider configurations and native report owner.

The former bare `typos` hook existed only in the Make recipe, help and tests,
always under `|| true`. This branch declares no canonical typos runner,
configuration or provisioned toolchain capability. Removing that ownerless
best-effort advertisement removes no supported acceptance capability: it never
contributed a truthful verdict. Registered rule diagnostics remain unchanged;
no dictionary, installation, provider or suppression replaces the hook.
The pre-gate remains bounded; full `make check` is still required acceptance.

Trailing comma layout has one owner: Ruff's formatter. The tooling SSOT records
the removal of redundant `missing-trailing-comma` (COM812) lint enforcement using
its official rule name and rationale. This must be regenerated before runtime
validation; changing the SSOT alone does not update existing projections.

Selected functional gates remain blocking. `make check` fails when the selection
contains no projects or when a selected project has no `pyproject.toml`; no project is
skipped silently.

Local runs, CI, and hooks derive their gates from the same active set: `CI=N make check`
runs the intersection with `make.ci.local_check_gates`, `CI=Y make check` runs the
complement, and `make check` without `CI` runs the union. The configuration excludes
Mypy, Pyright, codemod and smells from CI, including advisory execution. Lint and
remaining type findings follow `make.ci.informative_check_gates`: native `FINDINGS`
remain reported without stopping tests; native `ERROR`, malformed reports, runtime
failures and functional findings remain blocking. The `check` pre-push hook drops
the inherited `CI` to run every active gate.

Every workspace and standalone projection exposes `make pre-commit`. CI and the
generated pre-commit hook invoke that same approval owner. Its typed workflow is
`setup -> audit -> check -> test`, with the configured CI token enforced before
topology or activation, even when the caller supplied a local token. Help, dry-run,
question, touch and custom approval replacements cannot yield an approval receipt.
Audit is read-only conformance and installed-lock provenance, not generation or a
dirty-tree check; legitimate staged changes are not rejected simply for being staged.

CI setup always reconciles the owned physical environment through locked,
noneditable installation, including an existing venv. It does not initialize,
activate or operate on members, and uses root-declared topology rather than reading
sibling manifests. Local setup without the CI token retains local source routing.
Only local upgrade resolves or writes locks; setup preserves the first install error
without retrying under a different lock mode.

Normal test verbs remain incremental testmon only and omit the configured slow
markers. The filesystem cache lives at the typed XDG/HOME-derived project path.
Actions restores only that project database and saves only on an allowed integration
push with a fresh completed-run path/digest/saveability receipt. The SQLite owner
checkpoints and checks integrity before the runner releases its lease and exports
the receipt. PRs, forks, cancelled or incomplete runs cannot publish cache state;
a completed failing test run may save without changing its failing status.

`smells` is not part of the `make check` partitions. The selector-free `make smells`
verb runs only the qlty smell scan and fails when it finds defects. The
`runtime-census` gate stays in `make check` and grades every runtime enforcement
finding, including rules that qlty also classifies as smells. An empty or
malformed qlty SARIF response is a failed scan, not a zero-finding receipt.
Native primary source spans and all `relatedLocations` pass through the typed issue
and SARIF report contracts without dropping comparison locations outside the primary
project. Coordinates are emitted only when the scanner supplies them, including explicit
zeros; line-only and regionless native locations do not acquire invented coordinates.
Point-only diagnostics from other gates remain point-only. The Markdown summary still
uses the primary location, while the SARIF artifact carries the comparison evidence.

## Census consumer evidence

The public refactor census report retains `Object.all_reference_sites` separately
from `runtime_reference_sites` and `script_reference_sites`. Each evidence site
includes the Rope character offset, path, line and surface. Exact path/offset
identities are deduplicated and sorted deterministically; distinct references on
the same line remain distinct. Every hit's absolute path and nonnegative character
offset are validated before definition filtering. Evidence excludes a definition only by
its exact normalized path/offset; the older line/path fallback remains confined
to reachability counts. Indexed source, script, test and example consumers and
static `__init__.py` reexports are retained,
including occurrences of private names and facade members.

This is report-only migration evidence, not a change to production reachability.
The existing reachability resource eligibility, line-level deduplication, private
and facade exclusions, test/example exclusions and reexport exclusions still own
the old counts and unused/removal classification. All-surface evidence must never
be interpreted as permission to delete a helper or as a dynamic closure proof.

`reference_evidence_collected` distinguishes an empty collected result from a
disabled search (`include_references=False`, or census rule selection without
`unused`). Evidence covers only the active Rope workspace's indexed files and its
existing name-index candidate selection. Untracked files in indexed wrapper
surfaces participate; ignored paths, nested ungoverned repositories, files outside
the workspace, alias-only downstream files without the original identifier, and
reflection/dynamic imports are not proven covered. Lazy export strings are not
semantic reexport occurrences. Source and reference-resolution failures propagate;
definition-token candidates are checked against the inventoried Rope binding using
the existing Rope identity comparator, not selected by spelling order. Separate
function/parameter bindings on a declaration line remain separate. If multiple
tokens on that line resolve to the same binding (for example, a one-line declaration
and use), the search fails with explicit ambiguity instead of guessing the
definition. An unlocatable definition identifier or occurrence without an absolute
path/valid offset fails instead of producing an apparently complete empty report.
A collected result is therefore bounded static evidence, never a whole-program
absence proof. Collecting
private/facade evidence expands reference-resolution work but adds no scanner or
registry.

## Bounded Mypy failure status

The Linux Mypy command applies `prlimit` before launching the checker. In the observed
Mypy 2.3.1 run, an exhausted plugin allocation produced `INTERNAL ERROR` and exit status
2;
[the tagged Mypy source](https://github.com/python/mypy/blob/v2.3.1/mypy/main.py#L167-L174)
assigns status 2 to blocking internal errors. This is version-specific behavior, not a
fixed expectation for later Mypy releases. The resource test requires the workload to
start, then a nonzero raw status and a diagnostic without a timeout; it never rewrites
the result into a synthetic `MemoryError` or success. The Darwin supervisor can instead
terminate a process whose resident memory exceeds its limit.

## Abstraction-boundary project identity

The boundary gate reads the declared project identity through
`u.Infra.read_project_metadata_result`. Owner exemptions and TOML allowances use that
typed identity, so renaming a checkout or creating a linked worktree does not change its
policy. A consumer placed in an owner's named directory remains a consumer. Missing or
malformed project metadata blocks the gate and preserves the metadata reader's
diagnostic; directory names are never identity fallbacks.

## Codemod scanner contract

Every codemod policy finding blocks the gate, whatever its rule severity. Failed rule
discovery, failed scanner execution, incomplete output, and invalid diagnostic payloads
block as native failures with their own diagnostics.

The gate consumes the complete native `ast-grep scan --json=compact` array. The
[documented scan contract](https://ast-grep.github.io/reference/cli/scan.html) and
[native diagnostic schema](https://ast-grep.github.io/guide/tools/json) distinguish a
completed scan with error-severity findings (exit 1) from a completed scan without
error-severity findings (exit 0). Exit 1 must carry only ast-grep's complete terminal
diagnostic, whose count equals the validated error-severity findings. Additional
traversal diagnostics remain blocking: ast-grep can continue after an unreadable path
and still return exit 1 because another file contains a finding. The scanner boundary
checks the
[native terminal diagnostic](https://github.com/ast-grep/ast-grep/blob/0.45.3/crates/cli/src/utils/error_context.rs#L200)
and rejects extra output from the
[native path worker](https://github.com/ast-grep/ast-grep/blob/0.45.3/crates/cli/src/utils/worker.rs#L92).
Timeouts, forwarded signals, other exit codes, malformed JSON, and disagreement between
exit code and diagnostic severities remain failures, even when stdout exists. Both
whole-project checks and `check_files` scan every elected provider rule.

AST replacements publish through the authenticated file-plan boundary, then reuse
the import normalizer on only the rewritten files. Unused imports and formatting
are normalized before the next mod check; normalization failures remain blocking.
The root facade export rule preserves literal tuple values and order while removing
an unnecessary type-only annotation dependency. It does not change classes, aliases
or inheritance, and it does not rewrite initializer projections.

`GateExecution.issues` retains each finding's original file, position, rule, message,
and severity. SARIF reports each finding at its native level; raw scanner output remains
available on the execution. A passing gate therefore proves both the scanner contract
and zero rule findings.

The same repair validates projected Ruff first-party namespaces strictly: a malformed
value cannot be replaced with discovered namespaces. A declared empty list remains
empty; namespace discovery applies only when the list is absent. A bare Python
annotation does not replace an existing facade binding. Mypy's module-specific
`follow_untyped_imports` policy analyzes Rope's installed source without suppressing
`import-untyped`; the typed tooling policy owns both template and dependency-modernizer
projections. See the
[Mypy option contract](https://mypy.readthedocs.io/en/stable/config_file.html#follow-untyped-imports).
