# Mypy resource limits

<!-- TOC START -->

- No sections found

<!-- TOC END -->

The same validated memory (MiB) and wall-time (seconds) settings apply on Linux and
macOS. The platform owns the mechanism:

- Linux keeps GNU `timeout` and `prlimit --as` unchanged: the kernel limits each
  process's virtual address space.
- macOS uses the bundled Python supervisor and native `/bin/ps`. It samples the combined
  resident memory (RSS) of the checker process group every
  `c.Infra.MYPY_SUPERVISOR_POLL_SECONDS` and terminates the group when the configured
  threshold or deadline is reached. This is a sampled
  termination threshold, not a kernel allocation barrier; transient memory overshoot and
  sampling latency are possible. Virtual mappings are not charged as resident memory.
  Descendants must remain in the group.

Every caller supplies a typed `m.Infra.MypyInvocation` with source paths, optional
configuration, diagnostic format, progress and profiling destinations. The resource
owner constructs the current interpreter's Mypy entrypoint. Protected edits identify
their destination workspace instead; the owner resolves its installed Mypy console
entrypoint, preserving that tool's environment. Profiling uses the managed Python.
Missing managed tools fail explicitly. No executable path enters the request. Source
paths follow the option terminator, so a path cannot become a checker option. The Darwin
supervisor accepts one validated invocation payload and rejects additional fields;
callers cannot select a different executable, Python program or module. Profiling uses
the same interpreter and checker arguments through the public `mypy.api.run` contract
under `cProfile`, preserving both diagnostic streams and the returned status. Mypy's CLI
uses a hard process exit that prevents an outer `cProfile` module from saving its
artifact; the public API's clean exit allows the profile to be written. The profiling
API buffers checker diagnostics until it returns. A terminated profile can therefore
lack both those diagnostics and its artifact; the resource failure remains a failure.
Normal checker runs retain their live native streams.

Darwin `RLIMIT_AS` is not interchangeable with Linux `prlimit`: the initial VM mappings
of an ordinary Python process can already exceed the Mypy budget, and Darwin rejects
lowering the limit below current usage. See Apple's
[resource-limit implementation](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_resource.c)
and Python's [resource documentation](https://docs.python.org/3/library/resource.html).

The supervisor uses the public CLI process owner to inherit the checker's input and
output and create its process group. Native accounting uses the same CLI command
boundary. The checker deadline starts after the accounting preflight; the invoking
runner's deadline also bounds supervisor imports and startup.

The supervisor preserves normal exit codes, reports deadline exhaustion as 124 and
memory exhaustion as 137, and forwards TERM, INT and HUP. Cleanup sends TERM (or the
received signal), then KILL after the configured grace period, including descendants
left after the checker exits. Accounting failures terminate the workload and propagate
the error; they never cause an unbounded execution. No GNU utility, extra package, or
shell shim is required on macOS.

The real deadline and resistant-descendant test scenarios use the configured slow
harness budget. Their checker deadlines reserve time for interpreter startup, the
runner's termination grace, and assertions. Local `make test` includes these cases; CI's
default marker policy excludes slow cases, so native macOS acceptance requires
`make test-full`, whose full phase includes every marker. A default CI test receipt
alone does not prove the supervisor's deadline and descendant behavior.
