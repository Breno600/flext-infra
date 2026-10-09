# Durable Git state capture

<!-- TOC START -->

<!-- TOC END -->

`u.Infra` owns scoped WIP capture. Callers select literal repository-relative paths in
`m.Infra.GitWorktreeStateRequest`; directories include their tracked and nonignored
untracked descendants. An empty path tuple captures nothing. Nested repositories retain
independent capture ownership.

`git_snapshot_worktree_state` measures the original HEAD, index entries, raw working
bytes, symlink text and permissions without modifying the source index. Unmerged,
intent-to-add, assume-unchanged and skip-worktree entries fail explicitly.
`git_verify_worktree_state` returns `ok(False)` for different layers in the same
repository at the same HEAD; identity mismatches and read failures return failures.

`git_checkpoint_worktree_state` retains separate index and working trees in a dedicated
Git reference. The working commit has the original HEAD and the index checkpoint as
parents and records the typed snapshot. Requested retained commits also become parents:
callers use the child repository's checkpoint to retain original parent gitlink HEAD,
index and working OIDs in that child's object database. Parent tree pointers alone do
not retain child objects. Repeating a request verifies the existing checkpoint; a
divergent reference is never overwritten. Temporary indexes live alongside the
repository's shared Git storage, never in a borrowed environment or the source index.

`git_apply_worktree_checkpoint` copies only those durable bytes into a sibling worktree.
Preflight permits the original baseline or the already-applied captured state for each
owned entry, enabling an interrupted operation to resume without overwriting unrelated
work. Gitlink OIDs are retained in trees and indexes; submodule directories are not
copied or reset. Their repositories must retain their own checkpoints and reconcile
their working HEAD independently. Clean destination regular files are recognized by Git
content and executable mode; their other permission bits need not match the source.
Applying the checkpoint restores the captured permission bits. Cleanup preserves
captured non-executable permission bits on surviving regular files while restoring
HEAD's executable mode. Git cannot recover historical permission bits it never stored.

After saving an evolved candidate, `git_verify_worktree_checkpoint_commit` checks the
original checkpoint independently and verifies the destination's current saved
descendant and clean owned scope. Candidate content may intentionally have changed after
capture. `git_publish_worktree_checkpoint` publishes the original reference with an
ordinary atomic push and checks its exact remote advertisement. It returns
`GitWorktreeCheckpointPublication`, binding the remote name, endpoint, reference and
object ID. Credential-bearing endpoints are rejected before they can enter a receipt.
Push retains Git's ordinary fast-forward concurrency rules; it never forces a reference
update. Publishing a branch alone does not preserve this reference remotely.

Only then may `git_cleanup_worktree_state` restore the owned source paths. Its required
`publication` argument is verified against the live endpoint and remote reference before
effects; configuration drift or a missing reference fails closed.
`git_verify_worktree_checkpoint_publication` provides the same live proof before
retiring a lane. Cleanup rejects changed source entries or unresolved nested worktrees
before effects and accepts already-completed cleanup entries on resumption. Staged
additions are removed from the source index without attempting to restore a nonexistent
HEAD path. Checkpoint references remain reachable after cleanup and lane retirement, so
staged-only content survives Git garbage collection.

Transitions acquire the canonical Git-root codegen journal lease and use guarded
physical file and symlink operations with per-entry content and identity checks.
Cooperative writers must use that same lease. This is not an atomic filesystem
transaction against arbitrary external writers; detected drift fails while the durable
checkpoint remains available for recovery.

The unscoped `git_copy_worktree_state` remains a copy primitive for existing generation
transactions: it preflights a pristine sibling at the same HEAD and applies separate
worktree and index patches. WIP uses durable scoped checkpoints to avoid capturing live
files that appeared after its ownership snapshot.

## Lane admission

`flext-infra workspace verify-lane --repo-root <checkout>` calls the same
`u.Infra.git_verify_lane` preflight used by branch creation, worktree creation,
branch publication, automated lane publication, branch retirement, and worktree removal.
It does not fetch, write refs,
refresh the index, create a lane, or retire one. `verify-clean` retains its separate
cleanliness contract.

The preflight rejects any stash entries or retained `refs/stash`, requires the
integration declaration from the checkout's typed workspace manifest, compares the
cached integration OID to its live remote advertisement, and proves ancestry before
checking the remote advertisement again. `--expected-tip <oid>` binds a later
verification to a prior observation; a changed tip is a refusal, never a retry.
Fetch and merge-forward recovery remain separate existing operations. Ordinary
`git_push_upstream` publication also requires absorbed live integration ancestry;
the durable checkpoint publisher remains its separate preservation owner and does
not acquire this admission gate.

The current native requests cannot authenticate Beads lane ownership, the previous
owned lane's integration, or retirement's published preservation and active-session
proofs. Consequently `--operation create` and `--operation retire` fail closed even
when the measured Git boundary is valid. No branch-name heuristic, caller boolean,
correlation row, or foreign-lane count substitutes for those proofs. Creation checks
run before directory creation; removal checks retain dirty, nested-submodule, and
lock protection and do not force removal or prune other registrations.

This boundary does not claim verified runtime stability, PR approval, authorized
retirement, or enforcement over arbitrary external Git commands. Checkpoint capture,
publication, and merge-forward remain available to consolidate existing work without
stash. Reopening admission requires the existing canonical ownership and preservation
protocols to reach the native mutation boundary, not another ledger or approval flag.

## Recovery Branches

`git_create_checkpoint_branch(checkpoint, publication, branch)` creates a history
alias of an actual checkpoint only after revalidating its live independent remote
retention and original scoped index/working bytes. It never switches HEAD, creates
a worktree, accepts a caller-selected start, or carries uncaptured WIP. Creation is
CAS-protected against an existing branch and uses the same writer lease as capture.
Managed `git_create_branch` remains fail-closed for unproven lane ownership.

`git_publish_checkpoint_branch` publishes only that exact captured commit without
force and verifies its live advertisement. `git_delete_checkpoint_branch` removes
only the remote alias on the exact retained-object lease, while rechecking that the
independent checkpoint remains published. Alias cleanup is not checkpoint retirement
or managed lane integration approval. The original source tree and index remain
unchanged; checkpoint scope remains explicit, not an assertion of global ownership.
