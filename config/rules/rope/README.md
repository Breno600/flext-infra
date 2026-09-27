# rope phase parameters (ADR-017)

Parameters and violation models for the rope phases of `make mod` (import-alignment,
accessor-renames, dataclass-modelizer, pydantic-presets, compat-alias, private-import,
future-annotations, class-nesting, deferred-models, contract-drift). Populated by cycles
C2 and C5 of the rope-modernize program (bead epic flext-exbwv); layer order stays in
`config/tooling.yaml` (`lazy-init.import-layer-order`).

`flatten-family-namespace-wrapper.yaml` declares the single-wrapper family rule. The
existing class-nesting phase consumes its typed operation and collision policy; it does
not create another mod loop or publication path. Planning uses a closed, read-only Rope
snapshot so proposed imports and inherited consumers share identities. Real entity
classes remain nested. A wrapper used as a value, an unresolved member, unresolved owner
inheritance, or a second prefix collision fails the complete plan. Receipts report the
exact wrapper and source-edit counts. Publication remains owned by the semantic
transaction, and generated facades remain owned by `make gen`.

The same class-nesting phase promotes shared behavior from private test fixtures to the
unique declared utilities facade of its tier. Rope resolves the original class and its
external consumers before planning a move; classes with pytest cases and unused helpers
keep their owners. The planner preserves declaration names, rejects ambiguous facades or
occupied destinations, and stages only content changes in the governed source inventory.
Existing nesting and publication complete the cutover; `make gen` updates the package
exports. When an existing export needs regeneration, run `make gen` before `make mod` so
the move observes the current public binding.

Quoted annotations are resolved before relocation loses the original binding, including
aliases imported through generated reexports. Rope elects the destination import; the
nesting step keeps `get_type_hints` bound to the moved class. Consumers used only in
type positions participate in the same plan. Ordinary literals, `Literal` values,
`Annotated` metadata, and unrelated homonyms retain their values.

Typing unification resolves names in concrete-syntax type positions through lexical
bindings. `Any`, `typing.Any`, and `object` do not establish JSON or attribute-probe
contracts; they remain visible to enforcement until their consumer defines the precise
type. Datetime and filesystem paths are not converted to JSON aliases. Imported facade
rewrites preserve ordinary strings, documentation, `Literal` values, and `Annotated`
metadata values, including quoted annotations and aliased typing imports. A referenced
callable may acquire its proven facade path without changing the metadata it produces.
Destination imports keep their declaration scope, and a competing or unproven facade
binding rejects the complete rewrite before publication. Structural type roots are
shared with family relocation, including quoted generic bases. Deferred strings inside
typing factory/cast calls that cannot be migrated by that selected path reject the
complete import rewrite; they never survive as orphaned references after their binding
is removed. Imports from another branch or a `TYPE_CHECKING` suite do not establish
runtime availability: each migrated declaration retains its original execution condition
unless a preceding import in the same suite proves availability.

Introducing a local facade import also requires that it cannot capture existing reads of
an ancestral binding, including reads in closures. Otherwise the source transaction is
rejected. Typing unification explicitly requires runtime availability, including for
`get_type_hints`, PEP 695 aliases, and Pydantic fields. Deferred, conditional, or late
imports do not prove it. A new import of the source file's owning package is also
rejected without an existing runtime binding, preserving package initialization order.
Consumers that explicitly require only type-checking bindings retain that behavior.
