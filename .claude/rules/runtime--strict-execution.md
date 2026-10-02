# Strict execution is universal and non-optional

Every project and projected agent applies all of these policies together:

- [fail loud](runtime--fail-loud.md);
- [no fallback](runtime--no-fallback.md);
- [preflight before effects](runtime--preflight-before-effects.md);
- [required environment](runtime--required-environment.md);
- [atomic effects](runtime--atomic-effects.md);
- [causal subprocess propagation](runtime--causal-subprocess.md);
- [no keyring](runtime--no-keyring.md);
- [zero residue](runtime--zero-residue.md).

The policies are cumulative. A project rule may make them narrower or reject more
inputs; it cannot relax, catch, normalize, skip, defer, or route around any of them.
Existing opposing behavior is a blocking violation to exterminate at its owner, never
grandfathered compatibility.

Resolve gate applicability before invocation. A dormant external-token gate is not
executed; selecting or invoking it applies every policy above.
