# Execution context

<!-- TOC START -->

- [Runtime is the authority](#runtime-is-the-authority)
- [Environment activation](#environment-activation)
- [Dependency locks](#dependency-locks)
- [Runtime environment](#runtime-environment)
- [Mise launchers](#mise-launchers)
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

Activation queries `bin-paths` from the installed, pinned Mise and prepends the real
tool directories to the host's shared shims. The query is isolated, offline, and
frozen: it neither installs tools nor changes locks. The `.envrc` also watches
`mise.version` and `mise.lock` to reload paths after `make upg`. A missing pin
requires `make upg`; a runtime that is not yet installed requires `make setup`, whose
provisioning happens before activation.

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
releases and writes the committed `uv.lock` and `mise.lock`. `make setup`, `make gen`,
and `make fmt` never upgrade: they install frozen from those locks, which is the CI
path. Git dependencies follow the tips of their declared integration branches, and `APPLY`
stays removed.

Each internal `flext-*` requirement declares its integration line in `pyproject.toml`,
never a commit: the resolved commit exists only in `uv.lock`, and only `make upg` moves
it to the line tip. The manifest does not pin revisions. A commit left in the
`pyproject.toml` projection is residue: `make gen` re-renders it on the detected line.
When the projection carries no line, a hand-written `project.flext_source` in the
manifest declares it, and a commit in a hand-written source fails. Fix the setup or
`upg` owner and regenerate through `make gen`; manual installs do not replace the cycle.

A workspace root declares each attached member, of any family, as an inline Git source
on the workspace's own integration line, the same line the governed `.gitmodules` requires
of that member. Only `flext-*` dependencies that are not members follow the FLEXT line.
The root `uv.lock` therefore resolves every member without a `[tool.uv.workspace]`
overlay.

## Runtime environment

Code in a checkout runs in the environment of its `RUNTIME_ROOT`. The generated Makefile
exports `RUNTIME_ROOT`, and flext-infra reads it as a typed declaration: the
`fresh-import` validation runs its probes with the Python of the external physical
environment the Makefile declares, never with the interpreter hosting the tool. Without
a declaration, the owner derives the checkout's Git root; a declaration without an
interpreter fails.

A member attached as a submodule uses the environment of its containing Git
superproject; a standalone checkout or linked worktree has its own. The physical
directory is `.venv` at the runtime root (`c.Infra.ENVIRONMENT_DIRECTORY`), never a
configuration value. The generated Makefile, the generated `.envrc`, and
`runtime_environment_dir` resolve that location from the same resolved runtime root, so
entering the checkout through a symlink does not change the selected environment. No environment is borrowed from another checkout
through a symlink.

## Mise launchers

`make upg` is also the only writer of `mise.version`, `bin/mise`, and `bin/mise.cmd`. It
resolves the Mise release once, through Mise itself (`mise latest github:jdx/mise`,
authenticated by `GITHUB_TOKEN` and subject to Mise's `minimum_release_age`), and
generates both launchers with `mise generate install-script --version <release>
--windows`, run by that release. Each launcher embeds the release and its checksums, so
direct, PATH, or shim calls never query the network to choose a version.
`mise.version` holds a generated header followed by the single release line.

`make gen`, `make check`, and CI only verify offline that the launchers embed the pinned
release. A workspace member receives an exact copy of that trio from the root
`make gen`, and only the runtime root runs `make upg`. The `flext_infra` package ships
its own trio under `templates/bootstrap/`, used only by a repository that has none or
still carries a projection whose launchers resolve `releases/latest` at run time: that
repository's `make gen` publishes the packaged, baked copy, and the next `make upg`
rewrites it for the resolved release. Never edit these files; the fix is `make upg`.

A project `bin/` never enters PATH (shell, `BASH_ENV`, or CI `GITHUB_PATH`): Mise binds
the shared shims to the first `mise` on PATH. Version the pin, `mise.lock`, and the
native graphs referenced under `.mise/locks/` together; for npm tools the graph contains
`package.json` and `aube-lock.yaml`. These files also enter the Docker context and
checkout fixtures. Frozen setup requires the graph and a valid digest, per the
[official Mise sidecar contract](https://mise.jdx.dev/dev-tools/mise-lock.html#native-dependency-sidecars).
Caches, installations, and local lock graphs stay out of Git. Never format or edit the
native payload: a byte change requires a new resolution through `make upg`.

The platforms declared by `toolchain.mise_lockfile_platforms` compose the lock together
with the platform of the machine running the upgrade, which Mise always includes.
Because `MISE_SAFE` ignores local settings, bootstrap forwards `MISE_LOCKFILE`,
`MISE_LOCKED`, and `MISE_LOCKFILE_PLATFORMS`, derived from the same typed owner.
`MISE_LOCKED` also enables the global guard against rewrites during installation;
`tool_config.locked` alone does not protect that boundary. The setup proof uses empty
Mise storage and verifies the bytes of the locks, the pin, and the whole native graph
after installation.

After resolving the Mise release, bootstrap keeps that version for every call of the
same operation and the recursive lifecycle. `upg` initializes the declared gitlinks
before resolving the Python locks. Other runtime-dependent verbs reject a missing or
unresolved pin before activation; `help` and `clean` remain local operations without
that dependency.

## SonarCloud exclusions

The committed-lock contract also removes the former SonarCloud exclusion for a missing
lock. `codegen.sonarcloud.issue_exclusions` remains the single source of the server
configuration. With `SONAR_TOKEN` in the environment, `make sonarcloud-sync` sends a
non-empty list through the `settings/set` API; an empty list uses
[`settings/reset`](https://sonarcloud.io/web_api/api/settings/reset) with `component`
and `keys`. The command rereads `settings/values` and requires the exact effective
value, including inherited exclusions. If the reset reveals an exclusion from a higher
level, the divergence remains a failure. A false positive on the native
`aube-lock.yaml` format requires individual adjudication with frozen-install proof; it
never authorizes broad exclusions or changes to the native payload.

## Bootstrap credentials

Network bootstrap receives an explicit credential in the process environment: `GH_TOKEN`
takes precedence over `GITHUB_TOKEN`. Make never queries `gh` or the keyring. Without
either, `make setup` may reuse already provisioned tools and dependencies; an operation
that needs the network fails in the owning backend. An invalid token preserves the
backend's native error, without an anonymous retry or source switch. Mise reads the same
`GITHUB_TOKEN`; Make removes any inherited `MISE_GITHUB_TOKEN` from recipe environments,
because an alias of the same credential would take precedence over it. The credential
launcher or CI job must inject `GITHUB_TOKEN` into the process; containers receive the
variable or BuildKit secret explicitly.

## Evidence and checkpoints

Each piece of evidence identifies command, directory, observed revision, exit code, and
decisive result. A run that is in progress, interrupted, or missing its exit code is not
green. Concurrent changes require a fresh read before writing and revalidation of the
affected paths. A published work-in-progress commit preserves work and enables review;
completion requires integration and runtime measured at the integrated SHA.

For namespace automation, investigate catalog, classifier, transformation, publication,
and consumers in that order. The namespace laws are codemod catalog rules, so the
codemod gate is their one verdict. Preserve mutability, inheritance, imports, and collection; validate the
transformation through the public interface before widening the batch. Structural
refactors go through `make mod`.

## Check gate partitions

No check gate is suspendable: every finding of every selected gate blocks. The
namespace laws are rule data of the codemod catalog and block through the codemod
gate. `make check` fails when the selection
contains no projects or when a selected project has no `pyproject.toml`; no project is
skipped silently.

Local runs, CI, and hooks derive their gates from the same active set, preserving the
declared typing partition: `CI=N make check` runs the intersection with
`make.ci.local_check_gates`, `CI=Y make check` runs the complement, and `make check`
without `CI` runs the union. The `check` pre-push hook drops the inherited `CI` to run
every active gate; the hook's other verbs keep the local token. The CI workflow runs
both partitions without overlap. Validators keep their severity, and active functional
gates still require execution without warnings or residual findings.

`smells` is not part of the `make check` partitions. The selector-free `make smells`
verb runs the same analysis gate separately and fails when it finds defects.

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
