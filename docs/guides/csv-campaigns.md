# CSV rename campaigns

<!-- TOC START -->

<!-- TOC END -->

For a recovery that only needs declarative Sed text rules, run `make mod-text`
at the affected repository root. This public verb validates exact rule receipts,
checks Python syntax before publication, applies the authenticated text batch,
and verifies that no findings remain. It does not enter the Rope or ast-grep
phases of `make mod`. Repair a malformed rule in its authored YAML catalogue,
then replay through this verb; do not edit a generated projection.
Python files in governed source trees are scanned by default. A rule may also
declare a relative `include` glob ending in a file suffix to elect authored
Markdown or configuration text. The same authenticated inventory and atomic
publisher cover these files; a generated-file header rejects a direct rewrite.
Sed `include` and `exclude` scopes must be lists of non-empty strings. Scalar,
mapping, null, non-string, and blank entries fail before any publication; no
scope is expanded into characters or coerced into a glob. Omitted scopes retain
the typed rule defaults, and empty lists remain valid unrestricted selectors.
When a candidate's Python package cannot import, the healthy Infra provider
can run `make mod-text-candidate` after its workspace manifest declares exactly
one `candidate_bootstrap_targets` entry. The same target declaration also
supports `make bootstrap-candidate` to project the declared recovery surface.
For regexes that may match several identifiers, declare a named group and
`capture_equals: {keyword: expected_name}` in the rule. The engine validates
that the group exists and rejects a different captured value before publishing
any rewrite in the batch.
Sed rules may declare `distributions: [flext-infra]` to select consumers by
their validated `[project].name`. An omitted or empty selector applies to every
consumer. The packaged catalogue scopes both Infra and Cosmos Docgen rules to
their owning distributions, so external projects can compose their own rules
without inheriting another project's file requirements. A selected Markdown
include still fails if its source is absent; a missing project identity is an
error rather than an implicit match.
The project identity is parsed from one authenticated `pyproject.toml` snapshot,
using the same managed-conflict recovery and typed TOML validation as project
metadata. That snapshot remains a transaction input through publication, so a
concurrent identity change rejects the complete text batch.

Python identity migrations are not Sed rules. Native ast-grep captures carry
authenticated UTF-8 byte ranges; `resolved-symbol` binds that exact expression
to the module and expression declared in `arg`, and `same-binding` proves the
replacement expression in the occurrence's lexical scope. Neither predicate
resolves another same-spelling occurrence or uses a module-level binding for a
shadowed function parameter. Admission refuses rebound source and replacement
roots, intermediate attributes and ambiguous imported aliases rather than using
Rope's inferred last assignment as a reaching-definition proof. Its immutable
source graph carries descriptor-authenticated Python import-owner receipts into
the guarded semantic publisher. All read-only dependency states must still match
at the existing source barrier before any candidate is staged or written.
Strings, docstrings, `Literal` values and `Annotated` metadata retain their
contents, including PEP 695 and assignment-style aliases. Actual type operands
remain distinct from metadata; unrelated runtime assignments are not annotations.
Foreign NoProject-backed binding owners cannot establish an immutable identity
graph through the closed project's filesystem. They remain unsupported with no
fixer even when their read-only file receipts exist; receipts are not permission
to infer from opaque or mutable third-party state.

The codegen helper migration only fixes references when `u` already binds the
same canonical utilities class. A missing or different binding leaves a visible
non-fixable finding for the semantic import owner; the AST phase never invents
an import or overwrites a homonym. Its existing Rope import cleanup retires
imports only after their executable references have actually migrated.
The tool-error literal migration only fixes comparisons with a resolved canonical
outcome and an equivalent local `c` binding. The retired regex's other contexts
(including expected data and untyped issue-code comparisons) have no declared
consumer identity and are not eligible for automatic enum conversion. Executable
legacy comparisons retain non-fixable findings in either direction and for unequal
comparisons, without guessing a schema from the other operand's name. Unreferenced
legacy module imports likewise retain a semantic-adjudication finding. JSON
payloads are data, not code, even when a text replacement would leave Python
syntax valid. These bounded AST rules run through `make mod`, not `mod-text`.

The public `make mod` circuit reads `Infra.refactor_csv_campaigns` from the packaged
configuration. Each campaign keeps one `old,new` CSV as its rename source. Consumer
repositories, including repositories outside the FLEXT superproject, consume that same
declared campaign through their own root verb. There is no per-campaign executable and
no direct ast-grep write pass.
The CSV path is relative to the declaring config directory; any declared scan roots
are relative to the consumer repository. Absolute and parent-traversing declarations
fail during typed config validation; resolved paths that leave either owner through a
symbolic link fail during public composition before source publication.

`make mod-text` replays only the declared Sed text rules through the same authenticated
publisher used by `make mod`. It exists for recovery when a text rule has left an
authored Python file unparsable and the Rope phases cannot start. Every future Python
replacement is parsed before the atomic batch publishes, so a malformed block-scalar
replacement leaves all source files unchanged. After recovery, rerun `make mod`,
`make gen`, and the native checks; `mod-text` is not a substitute for the full circuit.

The public `infra.mod` operation resolves the typed campaign declarations and composes
the real CSV runner and Rope workspace through `p.Infra` ports. The mod service receives
those dependencies and the validated campaign inputs by constructor. `infra.apply_renames`
offers the same real runner for an explicit `m.Infra.ApplyRenamesInput`. The CLI route
renders progress and rename reports; the runner itself only returns typed results.

Before class nesting, `make mod` plans nested payload relocation against an immutable
Rope snapshot. The nested-payload rule admits data-only declarations by resolved
Pydantic ancestry, not the spelling of an imported base. The planner requires exactly
one existing authored model-family owner already composed by the public `m` facade;
missing, competing, occupied, or generated destinations are not created or guessed.
Bases, field/default expressions, configuration and docstrings move unchanged through
CST. There is no automatic raw-model-to-preset conversion. Behavior-bearing bodies,
settings subclasses, unknown class decorators, unresolved dependencies and test
fixtures are not automatic payload movers. Executable references and quoted type
positions follow Rope identity; ordinary strings, `Literal` values and `Annotated`
metadata remain payloads. Proposed runtime imports include only requested lazy-export
providers, and a new cycle rejects the entire plan before publication. Model owners
that already depend on the source utility must have that prerequisite repaired first.
Resolved Pydantic validators and computed fields retain their declaration semantics;
ordinary methods do not establish a DTO role. Quoted field types participate in import
dependency discovery, and a local binding capturing the elected facade refuses the
cutover instead of rewriting through that unrelated binding.

`bindings` maps CSV expression prefixes to current public Rope identities. An empty
prefix describes member names relative to an owner; a nonempty prefix describes
qualified CSV expressions. Rope resolves aliases and class inheritance against those
owners and verifies the replacement member exists. The retired member need not remain
importable. A homonym belonging to another object is not part of the campaign. Receiver
inheritance alone is insufficient: an overriding old member retains its independent
identity. An overriding destination or an independently owned intermediate namespace
blocks the proposed migration. A missing destination blocks the whole campaign before
publication; historical lists cannot be enabled before their definers publish the
destination contract.

`text_globs` explicitly selects non-Python documentation and configuration text.
`python_documentation` selects comments and actual module, class and function
docstrings, including concatenated string tokens. Executable string payloads are
preserved. `exclude_globs` declares additional projection exclusions. Every CSV driver,
configured managed file and recognized generated projection is excluded from mutation.
CSV data with another header is eligible only when explicitly declared as a text
surface. Manifest-declared template inputs retain their source identity even when they
emit a generated-file header; arbitrary files with a template suffix receive no such
permission. Inventory comes from the existing Git scope owner, including untracked files
and literal unusual filenames.

Identical duplicate CSV rows coalesce. Conflicting duplicates, identity mappings,
overlapping source patterns, cycles and cascading destinations are rejected. This
ensures every accepted campaign has a stable single-pass meaning.

Multiple declared roots supply explicit source folders to the existing Rope project
owner. The engine does not discover unrelated host repositories under their common
ancestor. Planning authenticates physical source identity and bytes, asks Rope for
in-memory changes, and merges only disjoint source spans. The existing semantic
publisher owns the recoverable transaction. Its acceptance callback reopens the driver
and performs a fresh campaign scan before commit. Driver drift or pending changes
rejects publication and rolls back this invocation's consumer changes; an independent
writer's driver change is preserved.

Reports count actual published paths and pending authenticated source edit spans. A
second unchanged invocation reports zero published paths only after a fresh scan. These
reports do not substitute for the repository's full generation, format, check, test and
runtime acceptance receipts.

The binding behavior follows Rope's documented
[restructuring wildcard contract](https://github.com/python-rope/rope/blob/master/docs/overview.rst#restructurings).
