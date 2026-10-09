# Assessment: `codegen/_conform` part-class chain vs the ADR-014 part shape

<!-- TOC START -->

- [The chain](#the-chain)
- [Verdicts](#verdicts)
- [Recommendation](#recommendation)

<!-- TOC END -->

Bead `flext-ypswb` (épico `flext-ewba4`, slice S8). Date: 2026-10-07.
Scope: assessment only — no rewrite proposed for landing; normalization
candidates are recorded for the slices that already touch those files.

## The chain

`FlextInfraCodegenConform` composes thirteen classes in one linear
inheritance chain (MRO depth 13, counting the facade and the
`FlextService`-derived base link at `bootstrap`):

| #   | Part (file)                    | Lines | Code | Cx  | Responsibility                                           |
| --- | ------------------------------ | ----- | ---- | --- | -------------------------------------------------------- |
| 0   | `conform.py` (facade)          | 89    | 44   | 9   | public entry, `settle_repository`, git peers             |
| 1   | `_conform/execute.py`          | 927   | 749  | 151 | transaction: plan→publish→verify, rollback, fixed point  |
| 2   | `_conform/plan.py`             | 318   | 272  | 45  | top-level planning dispatch per surface                  |
| 3   | `_conform/scaffold_plan.py`    | 388   | 331  | 58  | new-repository scaffold planning                         |
| 4   | `_conform/existing_plan.py`    | 703   | 613  | 137 | existing-tree planning (pyproject, managed files)        |
| 5   | `_conform/artifact_render.py`  | 539   | 416  | 63  | rendered artifact composition + overlays                 |
| 6   | `_conform/context_render.py`   | 556   | 419  | 69  | render context assembly                                  |
| 7   | `_conform/pyproject_policy.py` | 245   | 175  | 51  | `[MANAGED]`/`[CUSTOM]` merge policy                      |
| 8   | `_conform/file_plans.py`       | 191   | 133  | 28  | `CodegenFilePlan` construction                           |
| 9   | `_conform/beads_routes.py`     | 125   | 73   | 16  | beads config routing                                     |
| 10  | `_conform/docs_ownership.py`   | 87    | 43   | 9   | docs ownership mapping                                   |
| 11  | `_conform/gitignore.py`        | 46    | 22   | 0   | gitignore deny-first rendering                           |
| 12  | `_conform/bootstrap.py`        | 180   | 122  | 10  | base link (`s[m.Infra.CodegenResult]`), execution inputs |

Totals: 4,473 lines / 3,478 code / cyclomatic 647 (scc, this tree).

## Verdicts

1. **The shape is the idiomatic FLEXT part-class composition** (ADR-014
   §1.5): one responsibility per part file, the facade stays thin (44 code
   lines), the base link lands on the service preset. KEEP the chain; a
   composition rewrite (injected planners) is not justified by the
   evidence.
2. **No part exceeds `loc_cap`** (max 749 code lines in `execute.py`
   against the 1,000 ceiling) and no part is a god object: each carries
   exactly one planning/execution concern named by its file.
3. **Watch-item — `execute.py`** (749 code / cx 151): the transaction
   executor concentrates publish, verification, journal interaction and
   rollback. It is the only part where a further split (execution vs
   recovery) has an evidence base. Split it only in a slice that already
   touches it for behavioral reasons; a standalone split adds churn
   without a defect to cure.
4. **Watch-item — MRO depth 13**: the depth is the price of the
   part-class shape; every layer is a distinct concern and call sites
   within the chain are explicit (`self.<method>` resolved one layer up).
   The implicit cross-part state coupling this implies is the documented
   trade of ADR-014 §1.5, not a defect discovered here.
5. **No suppression, no compat seams, no dead links** were found in the
   chain; `_conform/__init__.py` is the generated lazy-export surface.

## Recommendation

No action in this epic. If a future slice rewrites `execute.py`, split
the rollback/recovery concern into `_conform/transaction_recovery.py` in
the same change; revisit MRO depth only if a fourteenth concern appears.
