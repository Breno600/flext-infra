"""Public transaction ownership across real processes and attached repositories.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import multiprocessing
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import c, config, m, p, r
from flext_infra.codegen.codegen_transaction import FlextInfraCodegenTransaction
from flext_infra.codegen.mise_artifacts import FlextInfraCodegenMiseArtifacts
from flext_infra.codegen.mise_artifacts_workspace import FlextInfraMiseWorkspacePlanner
from tests import u

if TYPE_CHECKING:
    from multiprocessing.synchronize import Event


class TestsFlextInfraTransactionLease:
    """Keep live journal recovery behind the shared physical scope lease."""

    @staticmethod
    @pytest.mark.parametrize("boundary", ["service", "cli"])
    def test_native_acquisition_denial_escapes_without_waiting(
        tmp_path: Path,
        boundary: str,
    ) -> None:
        """A Python audit policy denial is not kernel lock contention.

        The child installs a real audit hook instead of replacing flock.
        The public service and CLI preserve the exception and its traceback;
        the lease can then acquire the unchanged physical lock file.
        """
        root = u.Tests.git_repository(tmp_path)
        script = (
            "import errno, sys\n"
            "from pathlib import Path\n"
            "from flext_infra import infra, m, u\n"
            "from flext_infra.cli import main\n"
            "from flext_infra.codegen import FlextInfraMiseWorkspacePlanner\n"
            "root = Path(sys.argv[1])\n"
            "identity = u.Infra.git_identity("
            "m.Infra.GitRepoRequest(repo_root=root)).unwrap()\n"
            "journal = FlextInfraMiseWorkspacePlanner.journal_path(identity)\n"
            "original = OSError(errno.EPERM, 'audit policy denies lease')\n"
            "allowed = False\n"
            "def policy(event, arguments):\n"
            "    if event == 'fcntl.flock' and not allowed:\n"
            "        raise original\n"
            "sys.addaudithook(policy)\n"
            "try:\n"
            "    if sys.argv[2] == 'service':\n"
            "        infra.codegen_conform(m.Infra.CodegenConformRequest(root=root))\n"
            "    else:\n"
            "        main(['codegen', 'conform', '--root', str(root), "
            "'--scope', 'self', '--mode', 'apply'])\n"
            "except OSError as failure:\n"
            "    assert failure is original\n"
            "    assert failure.errno == errno.EPERM\n"
            "    assert failure.__traceback__ is not None\n"
            "else:\n"
            "    raise AssertionError("
            "'denied lease did not escape the public boundary')\n"
            "assert not journal.exists()\n"
            "lock = journal.with_name(journal.name + '.lock')\n"
            "before = lock.stat()\n"
            "allowed = True\n"
            "with u.Infra.codegen_transaction_lease(journal):\n"
            "    after = lock.stat()\n"
            "    assert (before.st_dev, before.st_ino) == "
            "(after.st_dev, after.st_ino)\n"
        )
        outcome = tm.ok(
            u.Cli.run_raw(
                [sys.executable, "-c", script, str(root), boundary],
                timeout=config.Infra.tooling.tools.pytest.case_timeout_seconds,
            ),
        )
        tm.that(
            u.Cli.process_succeeded(outcome.outcome),
            eq=True,
            msg=outcome.stdout + outcome.stderr,
        )

    @staticmethod
    def _ok_path(scope: Path) -> p.Result[Path]:
        """Trivial identity operation typed concretely for ``run_locked``.

        Why: passing the generic ``r[Path].ok`` classmethod directly loses its
        ``Path`` specialization at the call site (a second, independent type
        variable on ``ok`` itself), so a concretely annotated wrapper is the
        typed fix rather than widening ``run_locked``'s signature.

        Returns:
            The resulting ``p.Result[Path]``.

        """
        return r[Path].ok(scope)

    @staticmethod
    def _hold_transaction(root: Path, ready: Event, release: Event) -> None:
        """Publish a real prepared phase and commit after the contender finishes."""
        owner = FlextInfraCodegenMiseArtifacts(repository_root=root)
        transaction = FlextInfraCodegenTransaction(owner)

        def publish(scope_root: Path) -> p.Result[bool]:
            config_path = root / ".mise.toml"
            before = tm.ok(
                u.Cli.atomic_read_binary_file_state(config_path, required=True),
            )
            plan = m.Infra.CodegenFilePlan(
                project=root,
                path=config_path,
                before=before,
                desired_content=before.content,
                desired_mode=before.mode,
                owner="mise",
            )
            session = tm.ok(transaction.begin_locked(scope_root, (plan,), (plan,)))
            ready.set()
            tm.that(
                release.wait(config.Infra.tooling.tools.pytest.slow_timeout_seconds),
                eq=True,
            )
            tm.ok(
                transaction.commit_locked(
                    session,
                    lambda: owner.validate_artifacts(root, scope_root),
                ),
            )
            return r[bool].ok(value=True)

        tm.ok(transaction.run_locked(prepare=True, operation=publish))

    @staticmethod
    def _acquire_when_granted(scope: Path, acquired: Event) -> None:
        """Wait politely for the scope lease, then report the grant.

        flext-c2kp3: a same-scope contender must wait for a live holder instead
        of failing fast, so this child only publishes ``acquired`` once the
        kernel actually grants the lease.
        """
        owner = FlextInfraCodegenMiseArtifacts(repository_root=scope)
        transaction = FlextInfraCodegenTransaction(owner)
        tm.ok(transaction.run_locked(prepare=True, operation=r[Path].ok))
        acquired.set()

    @staticmethod
    def _member_workspace(tmp_path: Path) -> tuple[Path, Path, Path]:
        """Compose one governed workspace root with a submodule member.

        The workspace is the member's runtime root: it carries the triple.

        Returns:
            The workspace root, the member checkout, and one independent repo.

        """
        root = u.Tests.git_repository(tmp_path, "workspace")
        u.Tests.copy_tracked_mise_seeds(root)
        seed = u.Tests.git_repository(tmp_path, "member-source")
        u.Tests.copy_tracked_mise_seeds(seed)
        u.Tests.commit_git_changes(seed, "Seed declared Mise artifacts")
        u.Tests.git_bootstrap(
            root,
            (
                "-c",
                "protocol.file.allow=always",
                "submodule",
                "add",
                str(seed),
                "member",
            ),
        )
        member = root / "member"
        independent = u.Tests.git_repository(tmp_path, "independent")
        u.Tests.copy_tracked_mise_seeds(independent)
        return root, member, independent

    @staticmethod
    def _run_member_transaction(member: Path) -> None:
        """Run one full transaction against the held member scope."""
        owner = FlextInfraCodegenMiseArtifacts(repository_root=member)
        tm.ok(
            FlextInfraCodegenTransaction(owner).run_locked(
                prepare=True,
                operation=lambda scope: owner.validate_artifacts(member, scope),
            ),
        )

    @staticmethod
    def _run_independent_transaction(independent: Path) -> None:
        """Run one full transaction in the free scope while the lease is held."""
        independent_owner = FlextInfraCodegenMiseArtifacts(
            repository_root=independent,
        )
        tm.ok(
            FlextInfraCodegenTransaction(independent_owner).run_locked(
                prepare=True,
                operation=lambda scope: independent_owner.validate_artifacts(
                    independent,
                    scope,
                ),
            ),
        )

    @pytest.mark.slow
    def test_contenders_cannot_reconcile_live_journal_across_member_scope(
        self,
        tmp_path: Path,
    ) -> None:
        """A same-scope contender waits for a live holder; scopes are free."""
        root, member, independent = self._member_workspace(tmp_path)
        identity = tm.ok(u.Infra.git_identity(m.Infra.GitRepoRequest(repo_root=root)))
        journal_path = FlextInfraMiseWorkspacePlanner.journal_path(identity)
        lock_path = journal_path.with_name(f"{journal_path.name}.lock")
        context = multiprocessing.get_context("spawn")
        ready, release = context.Event(), context.Event()
        holder = context.Process(
            target=self._hold_transaction,
            args=(member, ready, release),
        )
        holder.start()
        waiter: multiprocessing.process.BaseProcess | None = None
        try:
            tm.that(
                ready.wait(config.Infra.tooling.tools.pytest.slow_timeout_seconds),
                eq=True,
            )
            journal_before = journal_path.read_bytes()
            lock_before = lock_path.stat()
            granted = context.Event()
            waiter = context.Process(
                target=self._acquire_when_granted,
                args=(member, granted),
            )
            assert waiter is not None
            waiter.start()
            # While the holder is live the contender stays blocked: it neither
            # acquires the lease nor touches the journal.
            tm.that(granted.wait(timeout=5.0), eq=False)
            tm.that(journal_path.read_bytes(), eq=journal_before)

            self._run_independent_transaction(independent)
            tm.that(journal_path.read_bytes(), eq=journal_before)

            # Releasing the holder hands the lease to the waiting contender.
            release.set()
            tm.that(
                granted.wait(
                    timeout=config.Infra.tooling.tools.pytest.slow_timeout_seconds,
                ),
                eq=True,
            )
            waiter.join(timeout=config.Infra.tooling.tools.pytest.slow_timeout_seconds)
            tm.that(waiter.exitcode, eq=0)
        finally:
            release.set()
            holder.join(timeout=config.Infra.tooling.tools.pytest.slow_timeout_seconds)
            tm.that(holder.exitcode, eq=0)
            holder.close()
            if waiter is not None:
                waiter.join(
                    timeout=config.Infra.tooling.tools.pytest.slow_timeout_seconds,
                )
                waiter.close()

        tm.that(journal_path.exists(), eq=False)
        lock_after = lock_path.stat()
        tm.that(
            (lock_after.st_dev, lock_after.st_ino),
            eq=(lock_before.st_dev, lock_before.st_ino),
        )
        self._run_member_transaction(member)
        tm.that(lock_path.stat().st_ino, eq=lock_after.st_ino)

    def test_file_participant_lease_lives_in_ignored_state_directory(
        self,
        tmp_path: Path,
    ) -> None:
        """Leasing a publication root adds no entry beside its tracked content."""
        root = u.Tests.git_repository(tmp_path)
        participant_root = root / "docs"
        participant_root.mkdir()
        u.Tests.copy_tracked_mise_seeds(root)
        before = {path.name for path in participant_root.iterdir()}
        transaction = FlextInfraCodegenTransaction(
            FlextInfraCodegenMiseArtifacts(repository_root=root),
        )

        tm.ok(
            transaction.run_files_locked({"@docs-0": participant_root}, self._ok_path),
        )
        tm.ok(
            transaction.run_files_locked({"@docs-0": participant_root}, self._ok_path),
        )

        tm.that(
            {path.name for path in participant_root.iterdir()} - before,
            eq={c.Infra.TRANSACTION_STATE_DIRNAME},
        )
        tm.that(
            [
                path.name
                for path in (
                    participant_root / c.Infra.TRANSACTION_STATE_DIRNAME
                ).iterdir()
            ],
            eq=[f"{c.Infra.JOURNAL_NAME}.lock"],
        )

    def test_operation_error_escapes_unchanged_and_releases_lease(
        self,
        tmp_path: Path,
    ) -> None:
        """Keep the original error object and allow ownership after an exception."""
        root = u.Tests.git_repository(tmp_path)
        transaction = FlextInfraCodegenTransaction(
            FlextInfraCodegenMiseArtifacts(repository_root=root),
        )
        original = OSError("operation failed under its lease")

        def fail(_scope: Path) -> p.Result[bool]:
            raise original

        with pytest.raises(
            OSError,
            match="operation failed under its lease",
        ) as failure:
            transaction.run_locked(prepare=False, operation=fail)
        tm.that(failure.value is original, eq=True)
        tm.ok(transaction.run_locked(prepare=False, operation=self._ok_path))
