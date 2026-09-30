"""Behavior: the worktree state checkpoint protects and publishes uncommitted state.

The checkpoint must make every staged, unstaged, and untracked blob reachable
from a named ref without touching HEAD, the index, or the working tree; the
capture is bounded by ignore rules, so ignored untracked material (secrets)
stays out while tracked-ignored paths stay in; the publication records the
remote tip and must equal the checkpoint commit; the verification fails once
the remote ref is gone or holds a commit the checkpoint never produced.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import m
from tests import TestsFlextInfraUtilitiesGitMixin as git_ui, u

if TYPE_CHECKING:
    from pathlib import Path


def _identity(source: Path) -> m.Infra.GitIdentityReport:
    identity = u.Infra.git_identity(m.Infra.GitRepoRequest(repo_root=source))
    tm.ok(identity)
    return identity.value


class TestsFlextInfraGitWorktreeStateCheckpoint:
    """The checkpoint protects index/working blobs; publish/verify round-trip."""

    def test_checkpoint_excludes_ignored_untracked_secrets_but_keeps_tracked_ignored(
        self, tmp_path: Path
    ) -> None:
        """Ignore rules bound the capture: untracked secrets stay out of the ref."""
        source = git_ui.git_repository(tmp_path, "source")
        (source / "debug.log").write_text("tracked-first\n", encoding="utf-8")
        git_ui.git_bootstrap(source, ("add", "debug.log"))
        git_ui.git_bootstrap(source, ("commit", "-m", "tracked log"))
        (source / ".gitignore").write_text(".env\ndebug.log\n", encoding="utf-8")
        git_ui.git_bootstrap(source, ("add", ".gitignore"))
        git_ui.git_bootstrap(source, ("commit", "-m", "ignore rules"))
        (source / ".env").write_text("API_TOKEN=super-secret\n", encoding="utf-8")
        (source / "debug.log").write_text("tracked-ignored-update\n", encoding="utf-8")
        ref = "refs/wip/checkpoint"

        checkpointed = u.Infra.git_checkpoint_worktree_state(_identity(source), ref)

        tm.ok(checkpointed)
        tree = git_ui.git_capture(source, "ls-tree", "-r", "--name-only", ref)
        tm.that(tree, lacks=".env")
        shown = git_ui.git_capture(source, "show", f"{ref}:debug.log")
        tm.that(shown.removesuffix("\n"), eq="tracked-ignored-update")

    def test_checkpoint_protects_state_without_touching_the_worktree(
        self, tmp_path: Path
    ) -> None:
        """Staged, unstaged, and untracked blobs become reachable behind the ref."""
        source = git_ui.git_repository(tmp_path, "source")
        (source / "base.txt").write_text("base\n", encoding="utf-8")
        git_ui.git_bootstrap(source, ("add", "-A"))
        git_ui.git_bootstrap(source, ("commit", "-m", "base"))
        (source / "staged.txt").write_text("staged-change\n", encoding="utf-8")
        git_ui.git_bootstrap(source, ("add", "staged.txt"))
        (source / "base.txt").write_text("unstaged-change\n", encoding="utf-8")
        (source / "untracked.txt").write_text("untracked\n", encoding="utf-8")
        head_before = git_ui.git_capture(source, "rev-parse", "HEAD")
        ref = "refs/wip/checkpoint"

        checkpointed = u.Infra.git_checkpoint_worktree_state(_identity(source), ref)

        tm.ok(checkpointed)
        checkpoint = checkpointed.value
        tm.that(checkpoint.checkpoint_ref, eq=ref)
        tm.that(git_ui.git_capture(source, "rev-parse", "HEAD"), eq=head_before)
        status = git_ui.git_capture(source, "status", "--porcelain")
        tm.that(status, has="A  staged.txt")
        tm.that(status, has="M base.txt")
        tm.that(status, has="?? untracked.txt")
        for name, content in (
            ("staged.txt", "staged-change"),
            ("base.txt", "unstaged-change"),
            ("untracked.txt", "untracked"),
        ):
            shown = git_ui.git_capture(source, "show", f"{ref}:{name}")
            tm.that(shown.removesuffix("\n"), eq=content)

    def test_publish_records_the_remote_tip_and_verify_confirms_it(
        self, tmp_path: Path
    ) -> None:
        """Publishing records the remote commit; verifying passes while retained."""
        source = git_ui.git_repository(tmp_path, "source")
        (source / "tracked.txt").write_text("tracked\n", encoding="utf-8")
        git_ui.git_bootstrap(source, ("add", "-A"))
        git_ui.git_bootstrap(source, ("commit", "-m", "base"))
        remote = git_ui.git_repository(tmp_path, "remote")
        git_ui.git_bootstrap(source, ("remote", "set-url", "origin", str(remote)))
        ref = "refs/wip/checkpoint"
        checkpointed = u.Infra.git_checkpoint_worktree_state(_identity(source), ref)
        tm.ok(checkpointed)

        published = u.Infra.git_publish_worktree_checkpoint(
            checkpointed.value, "origin"
        )

        tm.ok(published)
        publication = published.value
        tm.that(publication.checkpoint_ref, eq=ref)
        tm.that(publication.remote, eq="origin")
        tm.that(
            publication.published_commit,
            eq=checkpointed.value.checkpoint_commit,
        )
        verified = u.Infra.git_verify_worktree_checkpoint_publication(
            checkpointed.value, publication
        )
        tm.ok(verified)
        tm.that(verified.value, eq=True)

    def test_verify_rejects_a_remote_that_diverged_from_the_checkpoint(
        self, tmp_path: Path
    ) -> None:
        """A remote tip the checkpoint never produced cannot pass verification."""
        source = git_ui.git_repository(tmp_path, "source")
        (source / "tracked.txt").write_text("tracked\n", encoding="utf-8")
        git_ui.git_bootstrap(source, ("add", "-A"))
        git_ui.git_bootstrap(source, ("commit", "-m", "base"))
        remote = git_ui.git_repository(tmp_path, "remote")
        git_ui.git_bootstrap(source, ("remote", "set-url", "origin", str(remote)))
        ref = "refs/wip/checkpoint"
        checkpointed = u.Infra.git_checkpoint_worktree_state(_identity(source), ref)
        tm.ok(checkpointed)
        published = u.Infra.git_publish_worktree_checkpoint(
            checkpointed.value, "origin"
        )
        tm.ok(published)
        (source / "other.txt").write_text("divergent\n", encoding="utf-8")
        git_ui.git_bootstrap(source, ("add", "other.txt"))
        git_ui.git_bootstrap(source, ("commit", "-m", "divergent"))
        divergent = git_ui.git_capture(source, "rev-parse", "HEAD").strip()
        git_ui.git_bootstrap(
            source, ("push", "--force", "origin", f"{divergent}:{ref}")
        )
        forged = m.Infra.GitWorktreeCheckpointPublication(
            checkpoint_ref=ref,
            remote="origin",
            published_commit=divergent,
            published_at=published.value.published_at,
        )

        verified = u.Infra.git_verify_worktree_checkpoint_publication(
            checkpointed.value, forged
        )

        tm.ok(verified)
        tm.that(verified.value, eq=False)

    def test_verify_fails_once_the_remote_ref_is_deleted(self, tmp_path: Path) -> None:
        """A wiped remote ref no longer proves the capture is retained."""
        source = git_ui.git_repository(tmp_path, "source")
        (source / "tracked.txt").write_text("tracked\n", encoding="utf-8")
        git_ui.git_bootstrap(source, ("add", "-A"))
        git_ui.git_bootstrap(source, ("commit", "-m", "base"))
        remote = git_ui.git_repository(tmp_path, "remote")
        git_ui.git_bootstrap(source, ("remote", "set-url", "origin", str(remote)))
        ref = "refs/wip/checkpoint"
        checkpointed = u.Infra.git_checkpoint_worktree_state(_identity(source), ref)
        tm.ok(checkpointed)
        published = u.Infra.git_publish_worktree_checkpoint(
            checkpointed.value, "origin"
        )
        tm.ok(published)

        git_ui.git_bootstrap(
            remote, ("update-ref", "-d", ref, published.value.published_commit)
        )

        verified = u.Infra.git_verify_worktree_checkpoint_publication(
            checkpointed.value, published.value
        )
        tm.ok(verified)
        tm.that(verified.value, eq=False)
