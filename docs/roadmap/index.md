# Roadmap

<!-- TOC START -->

- [Current state](#current-state)
- [Namespace and runtime handoff](#namespace-and-runtime-handoff)

<!-- TOC END -->

Roadmap updates are generated from docs validation outputs.

## Current state

Reconciled against live sources on `0.12.0-dev` at
`a2bd0a7262a0eab84bd7e4c27f8bdd10de0d247a` (superproject gitlink
`676ae7aa3c7511ce3b133fdd31e43cfc49e7564f`). The CRG build referenced by older plans
does not exist in this checkout; the only valid CRG lives in the `rope-modernize`
worktree, built at `469b26b4e0b336e78548fef1fdcfca347f9c5d53`, which is an ancestor of
the current tip. Any structural claim must be re-derived from the current tree, never
from that stale graph.

| Item                                  | Live state                                                                                                                                                                                                                                                                                            | Evidence                                                       |
| ------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| `_lazy_analysis` defect               | **Still present.** `execute.py:376` creates `_lazy_analysis` from `lazy_analysis.value`, but `execute.py:598` passes it to `validate_phase_analysis_locked` while the method signature at `execute.py:573-580` accepts `lazy_analysis` as a parameter. The variable is out of scope at the call site. | `src/flext_infra/codegen/_conform/execute.py`                  |
| God modules                           | **Still present, unchanged.** `_models/config.py` 3.342 LOC, `codegen/conform.py` 2.996 LOC, `_utilities/_rope/source.py` 1.122 LOC, `codegen/codegen_transaction.py` 1.021 LOC, `_utilities/pyproject_conform.py` 1.011 LOC, `_utilities/census.py` 958 LOC.                                         | `wc -l` on current tip                                         |
| `surf-hornet` envrc landings          | **Not integrated.** `dce9192a0` (flext-infra) and `1e49d70841` (superproject) are not ancestors of `a2bd0a726`. Adopt only if re-proven on the current tip.                                                                                                                                           | `git merge-base --is-ancestor`                                 |
| `rope-modernize` one-writer lazy-init | **Not integrated.** `4ee618f59` and supercommit `a3793f9010` are not ancestors of `a2bd0a726`. Candidate adoption only.                                                                                                                                                                               | `git merge-base --is-ancestor`                                 |
| `aeolian-sodalite`                    | **Rejected.** PR #235 closed, branch far behind. Re-derive useful behavior tests on the current tip only.                                                                                                                                                                                             | Addenda `02-contribution-adoption-matrix.md`                   |
| Gas City Beads                        | **Sole authority.** No local ledger, no `none` backend as an alternate store.                                                                                                                                                                                                                         | Operator correction, addenda `03-gates-beads-and-conflicts.md` |
| Phases 3, 8                           | **Not started.** Canonical cycle and closure have no green evidence on the current tip.                                                                                                                                                                                                               | Plan §"Status das fases"                                       |

The authoritative execution state is Gas City: `flext-itpd1.2` owns the current
documentation/governance convergence and `flext-5fxu6.4` owns generator and enforcement
work. Workspace-local plans are session evidence, not portable links or a second queue.
Unresolved items recorded here are the `_lazy_analysis` scope mismatch, the god-module
cutover, full canonical gates, and fleet closure; none are proven resolved by any live
source.

## Namespace and runtime handoff

The detailed execution handoff is
[`namespace-automation-handoff-2026-09-14.md`](namespace-automation-handoff-2026-09-14.md).
Its opening table is the entry point; the body is historical evidence, not current
state. The current-state table above supersedes stale SHA, phase, and owner claims in
that document where live sources disagree.
