"""Durable directory authority for generation transaction effects.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config, m, p, r
from flext_infra.codegen import (
    FlextInfraCodegenTransaction,
    FlextInfraMiseArtifactsCandidates,
    FlextInfraMiseArtifactsJournal,
    FlextInfraMiseArtifactsVerification,
)
from flext_infra.codegen._mise_artifacts_state import FlextInfraMiseArtifactsState
from flext_infra.codegen.mise_artifacts import FlextInfraCodegenMiseArtifacts
from flext_infra.codegen.mise_artifacts_workspace import FlextInfraMiseWorkspacePlanner
from tests import t, u


class TestsFlextInfraTransactionDirectoryJournal:
    """Exercise creation and cleanup against real physical filesystem state."""

    _TRANSACTION_ID = "a" * 32

    @staticmethod
    def test_live_artifact_verification_preserves_native_read_failure(
        tmp_path: Path,
    ) -> None:
        """A configuration replaced by a directory retains its reader failure."""
        root = u.Tests.git_repository(tmp_path)
        u.Tests.copy_tracked_mise_seeds(root)
        owner = FlextInfraCodegenMiseArtifacts(repository_root=root)
        planner = FlextInfraMiseWorkspacePlanner(owner)
        layout = tm.ok(planner.layout_from_selectors(root, (".",)))
        plan = tm.ok(planner.snapshot(layout))
        config_path = layout.projects[0].config
        preserved = tmp_path / "preserved-mise-config"
        config_path.rename(preserved)
        config_path.mkdir()
        baseline = u.Cli.atomic_read_binary_file_state(
            config_path,
            required=False,
        )

        observed = FlextInfraMiseArtifactsVerification.live(owner, plan)

        tm.that(tm.fail(observed), eq=tm.fail(baseline))
        tm.that(config_path.is_dir(), eq=True)
        tm.that(preserved.read_bytes(), eq=plan.projects[0].config.before.content)

    @staticmethod
    @pytest.mark.parametrize("pending", [False, True])
    def test_read_only_file_readiness_never_recovers_a_pending_journal(
        tmp_path: Path,
        *,
        pending: bool,
    ) -> None:
        """Readiness proves current state without promoting or removing history."""
        root = u.Tests.git_repository(tmp_path)
        owner = FlextInfraCodegenTransaction(
            FlextInfraCodegenMiseArtifacts(repository_root=root),
        )
        roots = {"@readiness-0": root}
        if pending:
            session = tm.ok(
                owner.run_files_locked(
                    roots,
                    lambda scope: owner.begin_files_locked(scope, roots, ()),
                )
            )
            before = tm.ok(
                u.Cli.atomic_read_binary_file_state(
                    session.plan.layout.journal_path,
                    required=True,
                )
            )
            tm.fail(
                owner.run_files_locked(
                    roots,
                    lambda _scope: r[bool].ok(value=True),
                    prepare=False,
                ),
                has="pending",
            )
            tm.that(
                tm.ok(
                    u.Cli.atomic_read_binary_file_state(
                        session.plan.layout.journal_path,
                        required=True,
                    )
                ),
                eq=before,
            )
        else:
            tm.ok(
                owner.run_files_locked(
                    roots,
                    lambda _scope: r[bool].ok(value=True),
                    prepare=False,
                )
            )

    def test_generation_source_accepts_authenticated_hardlink(
        self,
        tmp_path: Path,
    ) -> None:
        """Journal an immutable dependency source materialized from a cache."""
        root = u.Tests.git_repository(tmp_path)
        u.Tests.copy_tracked_mise_seeds(root)
        mise_owner = FlextInfraCodegenMiseArtifacts(repository_root=root)
        planner = FlextInfraMiseWorkspacePlanner(mise_owner)
        layout = tm.ok(planner.layout_from_selectors(root, (".",)))
        plan = tm.ok(planner.snapshot(layout))
        cache_source = tmp_path / "cache-source.j2"
        installed_source = tmp_path / "installed-source.j2"
        cache_source.write_bytes(b"immutable template bytes")
        os.link(cache_source, installed_source)
        source = tm.ok(
            u.Cli.atomic_read_binary_file_state(installed_source, required=True),
        )

        journal = FlextInfraMiseArtifactsJournal.begin(
            plan,
            transaction_id=self._TRANSACTION_ID,
            sources=(("lazy-init", source),),
        )

        recorded = tm.ok(journal)
        tm.that(recorded.sources[0].link_count, eq=2)

    @staticmethod
    def test_staged_mode_mismatch_preserves_original_configuration(
        tmp_path: Path,
    ) -> None:
        """Reject a real staged mode mismatch without touching the rollback target."""
        root = u.Tests.git_repository(tmp_path)
        u.Tests.copy_tracked_mise_seeds(root)
        owner = FlextInfraCodegenMiseArtifacts(repository_root=root)
        planner = FlextInfraMiseWorkspacePlanner(owner)
        layout = tm.ok(planner.layout_from_selectors(root, (".",)))
        plan = tm.ok(planner.snapshot(layout))
        config_path = layout.projects[0].config
        before = tm.ok(u.Cli.atomic_read_binary_file_state(config_path, required=True))
        desired_mode = next(
            item.mode
            for item in config.Infra.codegen.managed_files
            if item.path == Path(config_path.name)
        )
        stage = tmp_path / "stage"
        stage.mkdir()
        staged_config = stage / config_path.name
        staged_config.write_bytes(tm.not_none(before.content))
        staged_config.chmod(desired_mode ^ stat.S_IWGRP)

        tm.fail(
            FlextInfraMiseArtifactsCandidates.publication_plan(plan.projects, (stage,)),
            has="staged Mise artifact mode differs",
        )
        tm.that(
            tm.ok(u.Cli.atomic_read_binary_file_state(config_path, required=True)),
            eq=before,
        )

    @staticmethod
    @pytest.mark.slow
    @pytest.mark.parametrize("change_config", [False, True])
    @pytest.mark.parametrize("alternate_mode", [False, True])
    def test_mise_commit_preserves_unchanged_publications(
        tmp_path: Path,
        *,
        change_config: bool,
        alternate_mode: bool,
    ) -> None:
        """Journal all staged files without rewriting unchanged live artifacts."""
        root = u.Tests.git_repository(tmp_path)
        u.Tests.copy_tracked_mise_seeds(root)
        mise_owner = FlextInfraCodegenMiseArtifacts(repository_root=root)
        owner = FlextInfraCodegenTransaction(mise_owner)
        layout = tm.ok(
            FlextInfraMiseWorkspacePlanner(mise_owner).layout_from_selectors(
                root,
                (".",),
            ),
        )
        config_path = layout.projects[0].config
        declared_mode = next(
            item.mode
            for item in config.Infra.codegen.managed_files
            if item.path == Path(config_path.name)
        )
        desired_mode = declared_mode ^ stat.S_IWGRP if alternate_mode else declared_mode

        def publish(
            scope_root: Path,
            *,
            change: bool = False,
        ) -> p.Result[t.VariadicTuple[Path]]:
            before = tm.ok(
                u.Cli.atomic_read_binary_file_state(config_path, required=True),
            )
            content = tm.not_none(before.content)
            if change:
                content += b"\n# transaction fixture update\n"
            plan = m.Infra.CodegenFilePlan(
                project=root,
                path=config_path,
                before=before,
                desired_content=content,
                desired_mode=desired_mode,
                owner="mise",
            )
            session = tm.ok(owner.begin_locked(scope_root, (plan,), (plan,)))
            return owner.commit_locked(
                session,
                lambda: mise_owner.validate_artifacts(root, scope_root),
            )

        tm.ok(owner.run_locked(prepare=True, operation=publish))
        tm.that(stat.S_IMODE(config_path.stat().st_mode), eq=desired_mode)
        before_state = tm.ok(
            u.Cli.atomic_read_binary_file_state(config_path, required=True),
        )

        written = tm.ok(
            owner.run_locked(
                prepare=True,
                operation=lambda scope: publish(scope, change=change_config),
            ),
        )

        tm.that(written, eq=(config_path,) if change_config else ())
        if change_config:
            tm.that(
                config_path.read_bytes(),
                eq=(
                    tm.not_none(before_state.content)
                    + b"\n# transaction fixture update\n"
                ),
            )
        else:
            tm.that(
                tm.ok(u.Cli.atomic_read_binary_file_state(config_path, required=True)),
                eq=before_state,
            )
        tm.that(layout.journal_path.exists(), eq=False)
        tm.that(layout.state_root.exists(), eq=False)
        tm.that(stat.S_IMODE(config_path.stat().st_mode), eq=desired_mode)

    @staticmethod
    def test_later_phase_backs_up_originals_beside_earlier_phase(
        tmp_path: Path,
    ) -> None:
        """Each phase that replaces an existing file owns a distinct backup."""
        root = u.Tests.git_repository(tmp_path)
        owner = FlextInfraCodegenTransaction(
            FlextInfraCodegenMiseArtifacts(repository_root=root),
        )
        roots = {"@docs-0": root}
        targets = {"conform": root / "first.md", "lazy-init": root / "second.md"}
        for phase, target in targets.items():
            target.write_bytes(f"{phase} original\n".encode())

        def two_phases(scope: Path) -> p.Result[t.VariadicTuple[Path]]:
            session = tm.ok(owner.begin_files_locked(scope, roots, ()))
            for phase, target in targets.items():
                plan = m.Infra.CodegenFilePlan(
                    project=root,
                    path=target,
                    before=tm.ok(
                        u.Cli.atomic_read_binary_file_state(target, required=True),
                    ),
                    desired_content=f"{phase} generated\n".encode(),
                    desired_mode=session.journal_state.mode,
                    owner=phase,
                )
                session = tm.ok(owner.append_phase_locked(session, phase, (plan,)))
            backups = [entry.original_backup for entry in session.journal.entries]
            tm.that(len(set(backups)), eq=len(targets))
            return owner.commit_locked(session, lambda: r[bool].ok(value=True))

        tm.ok(owner.run_files_locked(roots, two_phases))
        for phase, target in targets.items():
            tm.that(target.read_bytes(), eq=f"{phase} generated\n".encode())

    @staticmethod
    @pytest.mark.parametrize("foreign_change", [False, True])
    def test_duplicate_phase_recovers_only_its_new_generated_files(
        tmp_path: Path,
        *,
        foreign_change: bool,
    ) -> None:
        """Undo exact new publications, never a foreign replacement at their path."""
        root = u.Tests.git_repository(tmp_path)
        u.Tests.copy_tracked_mise_seeds(root)
        owner = FlextInfraCodegenTransaction(
            FlextInfraCodegenMiseArtifacts(repository_root=root),
        )
        target = root / "docs/generated/readme.md"

        def conflict(scope_root: Path) -> p.Result[m.Infra.CodegenTransactionSession]:
            config_path = root / ".mise.toml"
            before = tm.ok(
                u.Cli.atomic_read_binary_file_state(config_path, required=True),
            )
            config_plan = m.Infra.CodegenFilePlan(
                project=root,
                path=config_path,
                before=before,
                desired_content=before.content,
                desired_mode=before.mode,
                owner="mise",
            )
            session = tm.ok(
                owner.begin_locked(scope_root, (config_plan,), (config_plan,)),
            )
            session = tm.ok(
                owner.append_directories_locked(session, "docs", (target.parent,)),
            )
            first = m.Infra.CodegenFilePlan(
                project=root,
                path=target,
                before=tm.ok(
                    u.Cli.atomic_read_binary_file_state(target, required=False),
                ),
                desired_content=b"first phase\n",
                desired_mode=before.mode,
                owner="conform",
            )
            session = tm.ok(owner.append_phase_locked(session, "conform", (first,)))
            if foreign_change:
                target.write_bytes(b"foreign content\n")
            duplicate = m.Infra.CodegenFilePlan(
                project=root,
                path=target,
                before=tm.ok(
                    u.Cli.atomic_read_binary_file_state(target, required=True),
                ),
                desired_content=b"docs phase\n",
                desired_mode=before.mode,
                owner="docs",
            )
            return owner.append_phase_locked(session, "docs", (duplicate,))

        failed = owner.run_locked(prepare=True, operation=conflict)

        tm.fail(failed, has="multiple generation phases own one destination")
        identity = tm.ok(u.Infra.git_identity(m.Infra.GitRepoRequest(repo_root=root)))
        journal = FlextInfraMiseWorkspacePlanner.journal_path(identity)
        # Recovery consumes its journal on success in both branches: a foreign
        # file inside a journaled generated directory classifies noop (the
        # generation owns the path and rewrites it), so the cleanup preserves
        # that authenticated non-empty directory and the journal still closes.
        tm.that(journal.exists(), eq=False)
        if foreign_change:
            tm.that(target.read_bytes(), eq=b"foreign content\n")
            tm.that((root / "docs").exists(), eq=True)
            tm.that((root / "docs/generated").exists(), eq=True)
        else:
            tm.that((root / "docs").exists(), eq=False)
        tm.that((root / ".state").exists(), eq=False)
        tm.that(journal.with_name(f"{journal.name}.lock").is_file(), eq=True)

    @staticmethod
    @pytest.mark.slow
    @pytest.mark.parametrize("raises", [False, True])
    def test_failed_phase_after_begin_leaves_no_prepared_journal(
        tmp_path: Path,
        *,
        raises: bool,
    ) -> None:
        """A failing or raising phase after begin recovers under the same lease."""
        root = u.Tests.git_repository(tmp_path)
        u.Tests.copy_tracked_mise_seeds(root)
        owner = FlextInfraCodegenTransaction(
            FlextInfraCodegenMiseArtifacts(repository_root=root),
        )
        target = root / "generated.md"
        cause = OSError("docs preparation raised after begin")
        config_path = root / ".mise.toml"
        original = tm.ok(
            u.Cli.atomic_read_binary_file_state(config_path, required=True),
        )
        declared_mode = next(
            item.mode
            for item in config.Infra.codegen.managed_files
            if item.path == Path(config_path.name)
        )
        desired_mode = declared_mode ^ stat.S_IWGRP

        def failing_phase(
            _session: m.Infra.CodegenTransactionSession,
        ) -> p.Result[bool]:
            tm.that(target.read_bytes(), eq=b"prepared phase\n")
            tm.that(stat.S_IMODE(config_path.stat().st_mode), eq=desired_mode)
            if raises:
                raise cause
            return r[bool].fail("docs preparation failed after begin")

        def publish(scope_root: Path) -> p.Result[bool]:
            before = tm.ok(
                u.Cli.atomic_read_binary_file_state(config_path, required=True),
            )
            config_plan = m.Infra.CodegenFilePlan(
                project=root,
                path=config_path,
                before=before,
                desired_content=before.content,
                desired_mode=desired_mode,
                owner="mise",
            )
            generated = m.Infra.CodegenFilePlan(
                project=root,
                path=target,
                before=tm.ok(
                    u.Cli.atomic_read_binary_file_state(target, required=False),
                ),
                desired_content=b"prepared phase\n",
                desired_mode=before.mode,
                owner="conform",
            )
            session = tm.ok(
                owner.begin_locked(
                    scope_root,
                    (config_plan,),
                    (config_plan, generated),
                ),
            )
            return owner.publish_prepared_locked(session, failing_phase)

        if raises:
            with pytest.raises(OSError, match="raised after begin") as failure:
                owner.run_locked(prepare=True, operation=publish)
            tm.that(failure.value is cause, eq=True)
        else:
            tm.fail(
                owner.run_locked(prepare=True, operation=publish),
                has="docs preparation failed after begin",
            )
        identity = tm.ok(u.Infra.git_identity(m.Infra.GitRepoRequest(repo_root=root)))
        tm.that(
            FlextInfraMiseWorkspacePlanner.journal_path(identity).exists(),
            eq=False,
        )
        tm.that(target.exists(), eq=False)
        restored = tm.ok(
            u.Cli.atomic_read_binary_file_state(config_path, required=True),
        )
        tm.that((restored.content, restored.mode), eq=(original.content, original.mode))
        tm.ok(owner.run_locked(prepare=True, operation=r[Path].ok))

    @staticmethod
    def test_appended_phase_rejects_replaced_created_parent(
        tmp_path: Path,
    ) -> None:
        """Never adopt a foreign parent while staging a previously absent file."""
        root = u.Tests.git_repository(tmp_path)
        u.Tests.copy_tracked_mise_seeds(root)
        owner = FlextInfraCodegenTransaction(
            FlextInfraCodegenMiseArtifacts(repository_root=root),
        )
        target = root / "docs/generated/readme.md"
        preserved = root / "original-generated"

        def replace_parent(
            scope_root: Path,
        ) -> p.Result[m.Infra.CodegenTransactionSession]:
            config_path = root / ".mise.toml"
            before = tm.ok(
                u.Cli.atomic_read_binary_file_state(config_path, required=True),
            )
            config_plan = m.Infra.CodegenFilePlan(
                project=root,
                path=config_path,
                before=before,
                desired_content=before.content,
                desired_mode=before.mode,
                owner="mise",
            )
            session = tm.ok(
                owner.begin_locked(scope_root, (config_plan,), (config_plan,)),
            )
            planned = m.Infra.CodegenFilePlan(
                project=root,
                path=target,
                before=tm.ok(
                    u.Cli.atomic_read_binary_file_state(target, required=False),
                ),
                desired_content=b"owned content\n",
                desired_mode=before.mode,
                owner="docs",
            )
            session = tm.ok(
                owner.append_directories_locked(session, "docs", (target.parent,)),
            )
            target.parent.rename(preserved)
            target.parent.mkdir()
            return owner.append_phase_locked(session, "docs", (planned,))

        failed = owner.run_locked(prepare=True, operation=replace_parent)

        tm.fail(failed, has="generation destination parent differs from journal")
        tm.that(target.exists(), eq=False)
        tm.that(target.parent.is_dir(), eq=True)
        tm.that(preserved.is_dir(), eq=True)

    def test_begin_locked_preserves_residue_created_after_reconciliation(
        self,
        tmp_path: Path,
    ) -> None:
        """A held lease never grants ownership of newly appearing staging."""
        root = u.Tests.git_repository(tmp_path)
        u.Tests.copy_tracked_mise_seeds(root)
        mise_owner = FlextInfraCodegenMiseArtifacts(repository_root=root)
        owner = FlextInfraCodegenTransaction(mise_owner)
        config_path = root / ".mise.toml"
        before = tm.ok(u.Cli.atomic_read_binary_file_state(config_path, required=True))
        config_plan = m.Infra.CodegenFilePlan(
            project=root,
            path=config_path,
            before=before,
            desired_content=before.content,
            desired_mode=before.mode,
            owner="mise",
        )
        layout = tm.ok(
            FlextInfraMiseWorkspacePlanner(mise_owner).layout_from_selectors(
                root.resolve(),
                (".",),
                transaction_id=self._TRANSACTION_ID,
            ),
        )
        residue = tm.not_none(layout.projects[0].transaction_root)

        def begin_after_reconciliation(
            scope_root: Path,
        ) -> p.Result[m.Infra.CodegenTransactionSession]:
            residue.mkdir(parents=True)
            (residue / "orphan").write_bytes(b"journal-less staging")
            return owner.begin_locked(scope_root, (config_plan,), (config_plan,))

        tm.fail(
            owner.run_locked(prepare=True, operation=begin_after_reconciliation),
            has="no journal authority",
        )
        tm.that((residue / "orphan").read_bytes(), eq=b"journal-less staging")

    @pytest.mark.parametrize("unregistered_child", [False, True])
    def test_reconciliation_never_adopts_unjournaled_trees(
        self,
        tmp_path: Path,
        *,
        unregistered_child: bool,
    ) -> None:
        """Unregistered children are outside scope; in-scope residue fails closed."""
        root = u.Tests.git_repository(tmp_path)
        owner = FlextInfraCodegenTransaction(
            FlextInfraCodegenMiseArtifacts(repository_root=root),
        )
        participant = root / "unregistered" if unregistered_child else root
        participant.mkdir(exist_ok=True)
        layout = tm.ok(
            FlextInfraMiseWorkspacePlanner(
                FlextInfraCodegenMiseArtifacts(repository_root=root),
            ).file_layout(
                root,
                {"@docs-0": participant},
                transaction_id=self._TRANSACTION_ID,
            ),
        )
        residue = layout.file_participants[0].transaction_root
        residue.mkdir(parents=True)
        marker = residue / "foreign.bin"
        marker.write_bytes(b"not transaction-owned")
        before = tm.ok(u.Cli.atomic_read_binary_file_state(marker, required=True))

        result = owner.run_locked(prepare=True, operation=r[Path].ok)

        if unregistered_child:
            tm.ok(result)
        else:
            tm.fail(result, has="no journal authority")
        tm.that(
            tm.ok(u.Cli.atomic_read_binary_file_state(marker, required=True)),
            eq=before,
        )

    @staticmethod
    @pytest.mark.parametrize("with_foreign_file", [False, True])
    def test_phase_failure_preserves_preexisting_staging_root(
        tmp_path: Path,
        *,
        with_foreign_file: bool,
    ) -> None:
        """Failure to create a phase root cannot authorize deleting that root."""
        root = u.Tests.git_repository(tmp_path)
        owner = FlextInfraCodegenTransaction(
            FlextInfraCodegenMiseArtifacts(repository_root=root),
        )
        roots = {"@docs-0": root}
        target = root / "generated.md"

        def stage(scope_root: Path) -> p.Result[m.Infra.CodegenTransactionSession]:
            session = tm.ok(owner.begin_files_locked(scope_root, roots, ()))
            phase_root = (
                session.plan.layout.file_participants[0].transaction_root / "phase-docs"
            )
            phase_root.mkdir()
            if with_foreign_file:
                (phase_root / "foreign.bin").write_bytes(b"preserve")
            identity = phase_root.stat()
            planned = m.Infra.CodegenFilePlan(
                project=root,
                path=target,
                before=tm.ok(
                    u.Cli.atomic_read_binary_file_state(target, required=False),
                ),
                desired_content=b"generated\n",
                desired_mode=session.journal_state.mode,
                owner="docs",
            )
            failed = owner.append_phase_locked(session, "docs", (planned,))
            tm.fail(failed)
            tm.that(phase_root.stat().st_ino, eq=identity.st_ino)
            if with_foreign_file:
                tm.that((phase_root / "foreign.bin").read_bytes(), eq=b"preserve")
            tm.that(session.journal_state.path.exists(), eq=True)
            return failed

        tm.fail(owner.run_files_locked(roots, stage))
        tm.that(target.exists(), eq=False)

    @staticmethod
    @pytest.mark.parametrize("operation", ["append", "commit"])
    def test_same_content_journal_replacement_is_not_adopted(
        tmp_path: Path,
        operation: str,
    ) -> None:
        """Full-state CAS rejects a new inode even when journal bytes/mode match."""
        root = u.Tests.git_repository(tmp_path)
        owner = FlextInfraCodegenTransaction(
            FlextInfraCodegenMiseArtifacts(repository_root=root),
        )
        roots = {"@docs-0": root}
        target = root / "generated.md"

        def replace_journal(scope_root: Path) -> p.Result[bool]:
            session = tm.ok(owner.begin_files_locked(scope_root, roots, ()))
            journal = session.journal_state.path
            original = journal.with_suffix(".preserved")
            journal.rename(original)
            journal.write_bytes(original.read_bytes())
            journal.chmod(original.stat().st_mode)
            replacement = tm.ok(
                u.Cli.atomic_read_binary_file_state(journal, required=True),
            )
            if operation == "append":
                planned = m.Infra.CodegenFilePlan(
                    project=root,
                    path=target,
                    before=tm.ok(
                        u.Cli.atomic_read_binary_file_state(target, required=False),
                    ),
                    desired_content=b"generated\n",
                    desired_mode=session.journal_state.mode,
                    owner="docs",
                )
                tm.fail(
                    owner.publish_prepared_locked(
                        session,
                        lambda current: owner.append_phase_locked(
                            current,
                            "docs",
                            (planned,),
                        ),
                    ),
                    has="journal changed",
                )
            else:
                tm.fail(
                    owner.publish_prepared_locked(
                        session,
                        lambda current: owner.commit_locked(
                            current,
                            lambda: r[bool].ok(value=True),
                        ),
                    ),
                    has="journal changed",
                )
            tm.that(
                tm.ok(u.Cli.atomic_read_binary_file_state(journal, required=True)),
                eq=replacement,
            )
            tm.that(original.read_bytes(), eq=replacement.content)
            return r[bool].ok(value=True)

        tm.ok(owner.run_files_locked(roots, replace_journal))
        tm.that(target.exists(), eq=False)

    @staticmethod
    def _layout(root: Path) -> m.Infra.MiseToolchainWorkspaceLayout:
        root.mkdir()
        u.Tests.initialize_git_repo(root)
        (root / "bin").mkdir()
        owner = FlextInfraCodegenMiseArtifacts(
            repository_root=root,
            apply_changes=True,
            check_only=False,
        )
        planned = FlextInfraMiseWorkspacePlanner(owner).layout_from_selectors(
            root.resolve(),
            (".",),
            transaction_id=TestsFlextInfraTransactionDirectoryJournal._TRANSACTION_ID,
        )
        return tm.ok(planned)

    @staticmethod
    def _journal(
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        directories: t.VariadicTuple[m.Infra.CodegenJournalDirectory],
    ) -> m.Infra.CodegenTransactionJournal:
        physical = layout.scope_root.lstat()
        return m.Infra.CodegenTransactionJournal(
            version=8,
            transaction_id=TestsFlextInfraTransactionDirectoryJournal._TRANSACTION_ID,
            scope_device=physical.st_dev,
            scope_inode=physical.st_ino,
            state="prepared",
            projects=(
                m.Infra.CodegenJournalProject(
                    selector=".",
                    device=physical.st_dev,
                    inode=physical.st_ino,
                ),
            ),
            sources=(),
            directories=directories,
            entries=(),
        )

    @staticmethod
    def _materialize(
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        directories: t.VariadicTuple[m.Infra.CodegenJournalDirectory],
    ) -> t.VariadicTuple[m.Infra.CodegenJournalDirectory]:
        current = directories
        for intent in directories:
            created = tm.ok(
                FlextInfraMiseArtifactsState.create_journaled_directory(
                    layout,
                    current,
                    intent,
                ),
            )
            current = tuple(
                created if entry.path == intent.path else entry for entry in current
            )
        return current

    @classmethod
    def _register_manifest(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        directories: t.VariadicTuple[m.Infra.CodegenJournalDirectory],
    ) -> m.Infra.CodegenTransactionJournal:
        journal = cls._journal(layout, directories)
        registered = tm.ok(
            FlextInfraMiseArtifactsVerification.register_transaction_manifests(
                layout,
                journal,
            ),
        )
        recorded: m.Infra.CodegenTransactionJournal = tm.ok(
            FlextInfraMiseArtifactsJournal.record_directories(journal, registered),
        )
        return recorded

    def test_temporary_tree_is_journaled_before_creation_and_removed(
        self,
        tmp_path: Path,
    ) -> None:
        """Remove arbitrary regular staging files and every newly created parent."""
        layout = self._layout(tmp_path / "repository")

        planned = FlextInfraMiseArtifactsState.plan_transaction_directories(layout)

        directories = tm.ok(planned)
        tm.that((layout.scope_root / ".state").exists(), eq=False)
        directories = self._materialize(layout, directories)
        transaction_root = layout.projects[0].transaction_root
        assert transaction_root is not None
        (transaction_root / "partial-download").write_bytes(b"owned staging bytes")
        journal = self._register_manifest(layout, directories)

        cleaned = FlextInfraMiseArtifactsState.cleanup_journaled_directories(
            layout,
            journal,
            include_generated=True,
        )

        tm.ok(cleaned, eq=True)
        tm.that(transaction_root.exists(), eq=False)
        tm.that(layout.state_root.exists(), eq=False)

    def test_nonempty_generated_directory_is_preserved_and_rejected(
        self,
        tmp_path: Path,
    ) -> None:
        """Never infer ownership for an unexpected file in a live generated path."""
        layout = self._layout(tmp_path / "repository")
        target = layout.scope_root / "docs" / "generated"
        planned = FlextInfraMiseArtifactsState.plan_directories(
            layout,
            phase="docs",
            requested=(target,),
            disposition="generated",
        )
        directories = tm.ok(planned)
        directories = self._materialize(layout, directories)
        foreign = target / "foreign.txt"
        foreign.write_text("not journaled", encoding="utf-8")

        cleaned = FlextInfraMiseArtifactsState.cleanup_journaled_directories(
            layout,
            self._journal(layout, directories),
            include_generated=True,
        )

        tm.fail(cleaned)
        tm.that(foreign.read_text(encoding="utf-8"), eq="not journaled")

    @pytest.mark.skipif(os.name == "nt", reason="fixture symlink needs privilege")
    def test_transaction_symlink_is_preserved_and_rejected(
        self,
        tmp_path: Path,
    ) -> None:
        """Reject a transaction tree whose topology contains an alias."""
        layout = self._layout(tmp_path / "repository")
        directories = tm.ok(
            FlextInfraMiseArtifactsState.plan_transaction_directories(layout),
        )
        directories = self._materialize(layout, directories)
        transaction_root = layout.projects[0].transaction_root
        assert transaction_root is not None
        journal = self._register_manifest(layout, directories)
        (transaction_root / "alias").symlink_to(layout.scope_root)

        cleaned = FlextInfraMiseArtifactsState.cleanup_journaled_directories(
            layout,
            journal,
            include_generated=True,
        )

        tm.fail(cleaned)
        tm.that((transaction_root / "alias").is_symlink(), eq=True)

    def test_replaced_generated_directory_identity_is_preserved_and_rejected(
        self,
        tmp_path: Path,
    ) -> None:
        """Never delete a new empty inode placed at a journaled pathname."""
        layout = self._layout(tmp_path / "repository")
        target = layout.scope_root / "docs" / "generated"
        directories = tm.ok(
            FlextInfraMiseArtifactsState.plan_directories(
                layout,
                phase="docs",
                requested=(target,),
                disposition="generated",
            ),
        )
        directories = self._materialize(layout, directories)
        original = layout.scope_root / "original-generated"
        target.rename(original)
        target.mkdir()

        cleaned = FlextInfraMiseArtifactsState.cleanup_journaled_directories(
            layout,
            self._journal(layout, directories),
            include_generated=True,
        )

        tm.fail(cleaned)
        tm.that(target.is_dir(), eq=True)
        tm.that(original.is_dir(), eq=True)

    def test_foreign_file_after_manifest_is_preserved_and_rejected(
        self,
        tmp_path: Path,
    ) -> None:
        """Reject an unregistered descendant before applying any delete."""
        layout = self._layout(tmp_path / "repository")
        directories = self._materialize(
            layout,
            tm.ok(FlextInfraMiseArtifactsState.plan_transaction_directories(layout)),
        )
        journal = self._register_manifest(layout, directories)
        transaction_root = layout.projects[0].transaction_root
        assert transaction_root is not None
        foreign = transaction_root / "foreign.bin"
        foreign.write_bytes(b"foreign")

        cleaned = FlextInfraMiseArtifactsState.cleanup_journaled_directories(
            layout,
            journal,
            include_generated=True,
        )

        tm.fail(cleaned, has="unregistered")
        tm.that(foreign.read_bytes(), eq=b"foreign")

    def test_missing_registered_temporary_file_preserves_tree_and_fails(
        self,
        tmp_path: Path,
    ) -> None:
        """Do not normalize disappearance of a non-consumable journaled file."""
        layout = self._layout(tmp_path / "repository")
        directories = self._materialize(
            layout,
            tm.ok(FlextInfraMiseArtifactsState.plan_transaction_directories(layout)),
        )
        transaction_root = layout.projects[0].transaction_root
        assert transaction_root is not None
        payload = transaction_root / "registered.bin"
        payload.write_bytes(b"registered")
        journal = self._register_manifest(layout, directories)
        payload.unlink()

        cleaned = FlextInfraMiseArtifactsState.cleanup_journaled_directories(
            layout,
            journal,
            include_generated=True,
        )

        tm.fail(cleaned, has="missing")
        tm.that(transaction_root.is_dir(), eq=True)

    def test_crash_before_identity_persistence_preserves_unbound_tree(
        self,
        tmp_path: Path,
    ) -> None:
        """Never infer ownership from a pathname after the creation crash window."""
        layout = self._layout(tmp_path / "repository")
        directories = tm.ok(
            FlextInfraMiseArtifactsState.plan_transaction_directories(layout),
        )
        transaction_root = layout.projects[0].transaction_root
        assert transaction_root is not None
        transaction_root.mkdir(parents=True)
        marker = transaction_root / "unknown-owner.bin"
        marker.write_bytes(b"preserve")

        cleaned = FlextInfraMiseArtifactsState.cleanup_journaled_directories(
            layout,
            self._journal(layout, directories),
            include_generated=True,
        )

        tm.fail(cleaned, has="not journaled")
        tm.that(marker.read_bytes(), eq=b"preserve")
