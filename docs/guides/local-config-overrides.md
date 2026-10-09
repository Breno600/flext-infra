# Local config overrides (per-clone, gitignored)

<!-- TOC START -->

- [Contract](#contract)
- [Mandatory Mypy policy](#mandatory-mypy-policy)
- [List-typed registries](#list-typed-registries)
- [Example](#example)
- [Local dependency binding](#local-dependency-binding)
- [Candidate dependency commits](#candidate-dependency-commits)

<!-- TOC END -->

The flext-infra codegen ships a **public** fleet configuration: everything in
`config/*.yaml` is tracked, published, and safe for an external adopter. Values that are
operator-private — consumer organizations, deploy-key contracts, private workspace
layouts — must never be committed here. They live in one optional, gitignored file:

```
config/codegen-overrides.local.yaml
```

## Contract

- **Merge order**: tracked `config/*.yaml` files first (sorted), then the platform user
  overlay (`$XDG_CONFIG_HOME/flext-infra/*.yaml`), then `codegen-overrides.local.yaml`
  **last** — the local file wins every scalar collision.
- **Merge semantics**: identical to the tracked pipeline — recursive dict merge, lists
  concatenate, scalars replace. Dict-typed registries (`ci_private_submodules`,
  `layout.project_overrides`) gain local entries beside the public ones. The fleet
  supply-chain cooldown is one scalar (`toolchain.dependency_cooldown_days`) honoured by
  every resolver, never a per-repository map.
- **Validation**: the merged document passes the same typed models (`extra="forbid"`),
  so a typo in the local file fails loudly at load time instead of silently diverging.
- **Read timing**: the file is read once, when the config singleton is first fetched
  (module import of `flext_infra.config`). Restart any long-running process after
  editing it.
- **Never track it**: `.gitignore` blocks `/config/codegen-overrides.local.yaml` by SSOT
  rule; the guard gate rejects any diff reintroducing private values.

## Mandatory Mypy policy

`config/tooling.yaml` owns the declared Mypy policy and both projection paths consume
that same typed configuration. The project's Pydantic 2 contract requires the
`pydantic.mypy` plugin; missing, empty, or v1 resolved plugin declarations fail validation
rather than receiving a silent default.

The operator contract globally suspends only `prop-decorator` and `call-arg`. A complete
policy payload must declare both and cannot add another global suspension. The model
does not supply configuration-owned values through declaration defaults. Empty local
lists retain the tracked policy because the YAML loader concatenates lists. Pyright
call diagnostics and other unsuspended diagnostics remain active.

Generic Mypy options cannot replace `plugins`, `disable_error_code`, `python_version`,
`overrides`, or generated `mypy_path`. Reserved aliases and duplicate declarations
within or between the boolean and string maps fail validation. A string-valued
`enable_error_code` may enable unrelated diagnostics, but cannot re-enable any
suspended code, including within a comma-separated list. Boolean enabling is invalid.
Generic keys must be plain option identifiers, not quoted TOML keys or statements.
Global `ignore_errors = true` is forbidden; an explicit false boolean remains valid.
Dependency profiles in `config/codegen.yaml` restrict Pydantic to major version 2;
dependency locks and project manifests are regenerated through `make upg` and
`make gen`, respectively.

Regenerate consumers through canonical `make gen` after changing the source owner;
never patch generated pyprojects. Validate the public consumer with the plugin active
and an unsuspended negative diagnostic, then run the applicable native gates. A source
inspection, generation receipt, or merged PR alone is not proof of green delivery.

## List-typed registries

`providers` and `make.docs.github_repos` concatenate. A provider name must resolve
**exactly once** across the merged list, so never re-declare a name the tracked files
already carry — declare it in one layer only.

## Example

```yaml
Infra:
  codegen:
    providers:
      - name: my-org
        organization: my-org
        base_url: https://github.com/my-org
        branch: main
  release:
    publishable_prefixes:
      - my-repo-
```

Every governed standalone repository keeps referencing its provider by name from its own
`config/workspace.yaml`; the registry entry above is what lets the generator resolve it.

## Local dependency binding

The explicit `workspace flext-binding` CLI accepts `--repository-root`, `--flext-root`,
and `--python`. It changes only the provisioned consumer environment; it never edits the
consumer's dependency declarations. Canonical setup restores the declared resolution.
The interpreter must belong to the consumer's physical environment as determined by the
workspace topology. A symlinked environment or a foreign interpreter is rejected.

Binding evaluates dependency markers with that interpreter's facts and matches
normalized distribution names against the supplier root and its package members. Like
canonical setup, it includes all declared extras and dependency groups. Selected extras,
version bounds, declared constraints, and unrelated source overrides remain effective.
An empty active selection fails. CI rejects binding before accessing the consumer, using
the configured CI variable and value.

The public service's `plan_targets` method also requires the consumer `python` path;
planning must use the same interpreter as installation. Its in-repository callers use
that explicit contract, avoiding host-interpreter marker evaluation.

## Candidate dependency commits

An Infra integration lane can bootstrap declared candidate worktrees with
`make bootstrap-candidate`. Its handwritten `config/workspace.yaml` lists
`candidate_bootstrap_targets`, each with a relative `path` and a `what` value of
`makefile`, `docs-config`, `pyproject`, or `mise-triple`.
The verb uses the current branch-matched Infra generator and validates every target
as an exact Git worktree root. It plans all declared recovery projections before
starting one recoverable, multi-root publication, then verifies every target before
committing. A failed target
leaves the campaign unpublished. The integration manifest keeps this list empty; a
candidate campaign adds exact paths only in its worktree lane and removes them before
landing. An empty list
fails loud when the verb runs, rather than claiming a completed bootstrap. After
Makefile bootstrap, run `make setup` and `make gen` in that consumer's worktree.
The `pyproject` bootstrap regenerates declared tool tables through the existing
dependency conformance phases before Rope or uv reads the physical document. Project
metadata, dependency groups, and unowned tables remain live inputs; multiline string
contents never select a table. Normal generation and all gates still run afterward.
`docs-config` renders only the declared docs policy template when a conflicted
generated JSON file prevents ordinary generation from parsing it; afterward run
`make gen` to verify the full projection. Generated targets are never edited
directly. `mise-triple` restores the complete launcher and version-pin set from
the provider's validated packaged `make upg` artifacts in one publication when
a merge conflict prevents the candidate's Makefile from starting. Run `make upg`
in the candidate afterward to resolve its current release, then `make gen` to
project its managed files, including CI. The
`makefile` surface reads declared member identity from the workspace manifest even when
a member checkout has been initialized only partially and still lacks its
`pyproject.toml`; that is the state the new Make setup must repair. All other conform
surfaces continue to reject that incomplete member.

The public `codegen conform --what mise-config --scope self` recovery surface
regenerates only the selected checkout's `.mise.toml` from the canonical toolchain,
template, and declared project overlay. It snapshots the malformed destination as
raw bytes rather than parsing it as input. Apply holds the existing file transaction
lease and validates the journal-owned staged TOML before publication, then verifies
the live declaration and its fixed point. It installs no tools, changes no lockfile,
and rejects fleet scopes. Run the read-only `codegen mise-proof` for that checkout
before invoking a lifecycle command that requires its frozen installed toolchain.

A dedicated integration worktree may stage exact supplier commits in its handwritten
`config/workspace.yaml` under `candidate_dependencies`. Each entry declares the
distribution, its canonical HTTPS Git URL, and the full commit OID. This is a tracked,
reviewable candidate input, separate from the untracked local codegen override above.
The generator applies a candidate only to that distribution's direct Git requirement;
other dependencies stay on their declared integration lines. It rejects a URL that
disagrees with the member manifest or an existing direct requirement, and it cannot
introduce a Git source where neither declaration exists. An entry without a
corresponding direct requirement fails instead of being silently ignored. An omitted
`candidate_dependencies` list leaves normal release projections unchanged.

Candidate selection must include the published dependency closure. A direct pin in one
project cannot rewrite the metadata of another Git dependency: if `flext-tests` still
declares `flext-cli` on the integration branch, pinning `flext-cli` to a different
commit only in `flext-infra` makes `make upg` fail with conflicting Git URLs. Publish
candidate metadata from the supplier outward: generate and publish the `flext-cli`
commit first; generate, validate, and publish a `flext-tests` commit that declares that
exact CLI commit; then declare both immutable commits in the Infra consumer manifest.
Every dependent repository in a longer chain needs the same treatment before a later
consumer can resolve it. A candidate entry does not substitute for publishing the
intermediate repository's own generated metadata.

For each repository in that dependency order, use its dedicated worktree and physical
external environment. Run its canonical `make setup`, `make gen`, and `make upg`, then
`make setup` again to install the resolved lock. Run its native gates and repeat
`make gen` to prove a fixed point before publishing its candidate commit. If the
currently published Makefile cannot bootstrap that external environment, repair and
publish its canonical generator owner before this sequence; do not edit the generated
Makefile or create an internal environment. Remove candidate declarations through the
same manifest owner before promoting the normal integration line, and confirm `make gen`
returns the generated pyprojects to branch sources.
