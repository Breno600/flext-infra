# Local development and dependency upgrades

`make dev` executes the local workflow declared in `config.Infra.codegen.make.workflow`.
It provisions the environment with normal `make setup` resolution, generates project
files, formats and fixes code, checks the project, runs incremental tests, and builds
the package. Each operation must succeed before the next starts. Rewriting source
through `make mod` and running the full test baseline through `make test-full` remain
explicit operations.

`make upg` executes `config.Infra.codegen.make.upgrade_workflow`: setup, dependency
updates, another setup to install the resulting declarations, and generation. The
existing setup and dependency owners provision tools and resolve declared branches; this
lifecycle does not introduce a separate installer. Repository providers and dependency
branches remain those declared by the project.

The physical Git superproject owns the environment of an attached member, including
members whose declared Make profile is standalone. Local setup in a member synchronizes
its workspace environment. An independent checkout owns its own environment. These rules
also apply to toolchain resolution.

With `CI=Y`, setup leaves member checkouts untouched and installs packages from their
declarations without editable workspace sources. Operations select the current project
only. Existing environments are reused by operations that do not invoke setup, including
pre-commit checks. Explicit local editable binding through `FLEXT` is incompatible with
CI mode and fails before provisioning begins.

For local candidate development, `FLEXT` identifies an explicitly provisioned supplier
checkout. After every dependency sync, setup invokes the official
`workspace flext-binding` CLI using that supplier's physical environment, then continues
in the consumer's environment. The supplier must have its candidate installed editable
so the CLI executes its current source. This preserves the candidate binding even when
sync first reinstalls published dependencies. An attached supplier uses its physical
superproject's environment; no consumer environment or injected Python import path
supplies this CLI.

Binding retains dependency resolution while preserving the consumer's unselected PEP
621/735 requirements, including provider Git URLs and refs. Existing uv overrides and
manifest dependency revisions take precedence; uv constraints stay additive. Only
selected supplier distributions receive editable replacements. Ordinary requirements
remain additive constraints, so an incompatible candidate fails resolution. Only
explicit source, revision, and uv override declarations replace transitive requirements.
Binding queries PEP 508 facts once from the validated consumer interpreter, including
its exact Python and implementation versions, and uses those facts for every selection.
It selects active dependencies only and preserves their requested extras on local
install inputs. Revision pins are validated against complete declarations before
inactive inputs are omitted. The binding writes resolution inputs into an owned
temporary directory beneath the consumer's canonical external tool state and removes
that directory after the installer returns. Consumer declarations are never rewritten.
Canonical `workspace = true` sources resolve to provisioned physical members declared by
the consumer, retaining each member's editable setting. Selected candidates take
precedence over those sources. Poetry declarations and other unselected source forms
currently fail explicitly because the binding cannot faithfully translate them into
requirements. If input preparation or installation raises an exception, the original
exception escapes and the owned directory remains as failure evidence.

Provider migration is declared by `project.dependency_sources` in
`config/workspace.yaml`: each distribution maps to a direct Git requirement. Only named
dependencies change source; their extras and environment markers are preserved, and
`dependency_revisions` applies afterward. The named `flext-infra` source determines the
rendered FLEXT branch. Repository identities and unnamed dependencies remain unchanged.
`flext_source` selects the bootstrap supplier; it does not rewrite dependency providers.
Session binding consumes these same named source declarations before installing local
candidates.
