# Model-class boundary migration

<!-- TOC START -->

- No sections found

<!-- TOC END -->

`make mod` owns model-field access migration. The ast-grep rule reports dynamic
`model_fields` lookup; its semantic phase narrows an untrusted class argument using the
public `flext-core` model-class guard before accessing required fields.

A boundary that already rejects a missing or empty field mapping retains its original
rejecting branch. Non-model classes, model instances, and arbitrary objects reach that
branch without evaluating their `model_fields` attribute. Populated Pydantic model
classes continue through the boundary. Empty models remain invalid where the existing
boundary already required fields.

The migration discovers argument and local identities from the function source; there is
no project, filename, or function-name catalog. It also recognizes direct access emitted
by earlier versions of the textual rule. Ambiguous error branches, additional uses of
the temporary mapping, and conflicting guard bindings fail without publishing a partial
rewrite. Other dynamic lookups remain findings until their receiver contract is proven;
they are never blindly rewritten.

The codemod check gate blocks on every reported policy finding, whatever its rule
severity, and reports each finding with its native severity. Failed rule discovery,
incomplete scans, invalid diagnostics, and other native scanner failures also block,
with their own failure diagnostics.

The same semantic pipeline resolves elected self-facade imports before deferring them
into function bodies. Module/class execution, decorators, defaults and other eager uses
remain errors. Import identity comes from matched source and qualified bindings, not
diagnostic prose or a module-name catalog.

Dynamic environment reads require a resolved OS import and a config-owned key, either
directly or through an unambiguous same-function alias. The destination settings source
must declare both optional and required lookups. Optional reads retain `None` for
absence and preserve empty strings; required reads retain the native `KeyError`. Static
keys, rebinding and competing settings owners remain errors. Consumers are rewritten
only by `make mod`.

The upgrade interruption regression owns its child session through the CLI process
facade. Native procps selects that session's threads and proves the resolver is blocked
on the fixture FIFO before interruption. It never scans unrelated process directories or
discards a disappearing-process error. The test then verifies the original lock and
staging cleanup against the real upgrade implementation.

Rule snapshot changes are projected with `make mod-snapshots`. Run `make mod`,
`make gen`, and the native validation lifecycle after updating the automation
dependency. Do not repair the consumer by editing the rewritten call site.
