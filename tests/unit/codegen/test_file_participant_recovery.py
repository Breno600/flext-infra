"""Public recovery behavior for file-only transaction participants."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_core import r
from flext_infra import c, m, p, t, u
from flext_infra.codegen.codegen_transaction import FlextInfraCodegenTransaction
from flext_infra.codegen.mise_artifacts import FlextInfraCodegenMiseArtifacts
from flext_infra.validate import FlextInfraValidateFreshImport
from tests import u as test_u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraFileParticipantRecovery:
    """Recover prepared file-only journals through their physical owners."""

    def test_fresh_import_failure_restores_published_initializer(
        self, tmp_path: Path
    ) -> None:
        root = test_u.Tests.git_repository(tmp_path)
        package = root / c.Infra.DEFAULT_SRC_DIR / "flext_import_probe"
        package.mkdir(parents=True)
        initializer = package / c.Infra.INIT_PY
        initializer.write_text("__all__ = ()\n", encoding=c.Cli.ENCODING_DEFAULT)
        before = tm.ok(u.Cli.atomic_read_binary_file_state(initializer, required=True))
        owner = FlextInfraCodegenTransaction(
            FlextInfraCodegenMiseArtifacts(repository_root=root)
        )
        roots = {"@lazy-init": root}
        publication = tm.ok(
            u.Infra.planned_file(
                root,
                initializer,
                required=True,
                desired_content=b"__all__ = ('missing_export',)\n",
                desired_mode=before.mode,
                owner="lazy-init",
            )
        )
        validator = FlextInfraValidateFreshImport(
            repository_root=root, packages=(package.name,)
        )

        def publish(scope: Path) -> p.Result[t.VariadicTuple[Path]]:
            session = tm.ok(owner.begin_files_locked(scope, roots, (before,)))
            published = tm.ok(
                owner.append_phase_locked(session, "lazy-init", (publication,))
            )
            return owner.commit_locked(published, validator.execute)

        failed = owner.run_files_locked(roots, publish)

        tm.fail(failed, has="missing_export")
        tm.that(failed.error, has="Traceback")
        restored = tm.ok(
            u.Cli.atomic_read_binary_file_state(initializer, required=True)
        )
        tm.that(restored.content, eq=before.content)
        tm.that(restored.mode, eq=before.mode)
        tm.ok(owner.run_files_locked(roots, lambda _scope: r[bool].ok(True)))

    def test_recovers_external_only_prepared_journal(self, tmp_path: Path) -> None:
        workspace = test_u.Tests.create_docs_workspace(tmp_path, project_names=())
        docs_root = tmp_path / "published-docs"
        docs_root.mkdir()
        roots = {"@docs-0": docs_root}
        source = tm.ok(
            u.Cli.atomic_read_binary_file_state(workspace / "README.md", required=True)
        )
        transaction = FlextInfraCodegenTransaction(
            FlextInfraCodegenMiseArtifacts(repository_root=workspace)
        )

        prepared = transaction.run_files_locked(
            roots,
            lambda scope_root: transaction.begin_files_locked(
                scope_root, roots, (source,)
            ),
        )
        tm.ok(prepared)

        recovered = transaction.run_files_locked(
            roots, lambda _scope_root: r[bool].ok(True)
        )

        tm.ok(recovered)
        tm.that(recovered.value, eq=True)

    @pytest.mark.parametrize("foreign_change", ["none", "extra", "replaced"])
    def test_prepared_publication_recovery_requires_original_tree(
        self, tmp_path: Path, foreign_change: str
    ) -> None:
        """Recover owned publications, but retain foreign trees and their evidence."""
        root = test_u.Tests.git_repository(tmp_path)
        owner = FlextInfraCodegenTransaction(
            FlextInfraCodegenMiseArtifacts(repository_root=root)
        )
        roots = {"@docs-0": root}
        target = root / "generated.md"

        def prepare(scope_root: Path) -> p.Result[m.Infra.CodegenTransactionSession]:
            session = tm.ok(owner.begin_files_locked(scope_root, roots, ()))
            plan = tm.ok(
                u.Infra.planned_file(
                    root,
                    target,
                    required=False,
                    desired_content=b"owned publication\n",
                    desired_mode=session.journal_state.mode,
                    owner="docs",
                )
            )
            return owner.append_phase_locked(session, "docs", (plan,))

        session = tm.ok(owner.run_files_locked(roots, prepare))
        staging = session.plan.layout.file_participants[0].transaction_root
        tm.that(target.read_bytes(), eq=b"owned publication\n")
        if foreign_change == "replaced":
            staging.rename(root / "preserved-staging")
            staging.mkdir()
        if foreign_change != "none":
            (staging / "foreign.bin").write_bytes(b"preserve")

        recovered = owner.run_files_locked(roots, lambda _scope: r[bool].ok(True))

        if foreign_change == "none":
            tm.ok(recovered)
            tm.that(target.exists(), eq=False)
            tm.that(staging.exists(), eq=False)
            tm.that(session.journal_state.path.exists(), eq=False)
        else:
            tm.fail(recovered)
            tm.that((staging / "foreign.bin").read_bytes(), eq=b"preserve")
            tm.that(target.read_bytes(), eq=b"owned publication\n")
            tm.that(session.journal_state.path.exists(), eq=True)

    @pytest.mark.parametrize("with_foreign_file", [False, True])
    @pytest.mark.parametrize("journal_state", ["staging", "prepared"])
    def test_unmanifested_created_directory_owns_no_descendants(
        self, tmp_path: Path, journal_state: str, *, with_foreign_file: bool
    ) -> None:
        """A pre-manifest crash receipt permits only exact empty-directory cleanup."""
        root = test_u.Tests.git_repository(tmp_path)
        owner = FlextInfraCodegenTransaction(
            FlextInfraCodegenMiseArtifacts(repository_root=root)
        )
        roots = {"@docs-0": root}
        session = tm.ok(
            owner.run_files_locked(
                roots, lambda scope: owner.begin_files_locked(scope, roots, ())
            )
        )
        staging = session.plan.layout.file_participants[0].transaction_root
        crash_journal = m.Infra.CodegenTransactionJournal.model_validate({
            **session.journal.model_dump(),
            "state": journal_state,
            "directories": tuple(
                {**entry.model_dump(), "manifest": None}
                for entry in session.journal.directories
            ),
        })
        tm.ok(
            u.Cli.atomic_write_binary_file_guarded(
                session.journal_state,
                crash_journal.model_dump_json(indent=2).encode(c.Cli.ENCODING_DEFAULT),
                permission_mode=tm.not_none(session.journal_state.mode),
            )
        )
        if with_foreign_file:
            (staging / "foreign.bin").write_bytes(b"not journaled")

        recovered = owner.run_files_locked(roots, lambda _scope: r[bool].ok(True))

        if with_foreign_file:
            tm.fail(recovered)
            tm.that((staging / "foreign.bin").read_bytes(), eq=b"not journaled")
            tm.that(session.journal_state.path.exists(), eq=True)
        else:
            tm.ok(recovered)
            tm.that(staging.exists(), eq=False)
            tm.that(session.journal_state.path.exists(), eq=False)

    @pytest.mark.parametrize("journal_change", ["unchanged", "replaced", "missing"])
    @pytest.mark.parametrize("failure_kind", ["validator", "exception", "abort"])
    def test_session_failure_never_recovers_changed_journal(
        self, tmp_path: Path, failure_kind: str, journal_change: str
    ) -> None:
        """Retain the causal failure and publications when journal authority changes."""
        root = test_u.Tests.git_repository(tmp_path)
        owner = FlextInfraCodegenTransaction(
            FlextInfraCodegenMiseArtifacts(repository_root=root)
        )
        roots = {"@docs-0": root}
        target = root / "generated.md"
        cause = OSError("validator failed after journal replacement")

        def fail_validator() -> p.Result[bool]:
            if failure_kind == "exception":
                raise cause
            return r[bool].fail(str(cause))

        def fail_session(scope: Path) -> p.Result[bool]:
            session = tm.ok(owner.begin_files_locked(scope, roots, ()))
            plan = tm.ok(
                u.Infra.planned_file(
                    root,
                    target,
                    required=False,
                    desired_content=b"prepared publication\n",
                    desired_mode=session.journal_state.mode,
                    owner="docs",
                )
            )
            initial = session
            session = tm.ok(owner.append_phase_locked(session, "docs", (plan,)))
            before = tm.ok(u.Cli.atomic_read_binary_file_state(target, required=True))
            journal = session.journal_state.path
            saved = journal.with_suffix(".preserved")
            if journal_change != "unchanged":
                journal.rename(saved)
            if journal_change == "replaced":
                journal.write_bytes(saved.read_bytes())
                journal.chmod(saved.stat().st_mode)
            foreign = tm.ok(
                u.Cli.atomic_read_binary_file_state(journal, required=False)
            )
            if failure_kind == "exception":
                with pytest.raises(OSError, match=str(cause)) as raised:
                    owner.publish_prepared_locked(
                        initial,
                        lambda _initial: owner.commit_locked(session, fail_validator),
                    )
                tm.that(raised.value is cause, eq=True)
            else:
                failed = (
                    owner.abort_locked(session, str(cause))
                    if failure_kind == "abort"
                    else owner.publish_prepared_locked(
                        initial,
                        lambda _initial: owner.commit_locked(session, fail_validator),
                    )
                )
                tm.fail(failed, has=str(cause))
                tm.that(
                    "recovery_error" in (failed.error_data or {}),
                    eq=journal_change != "unchanged",
                )
            if journal_change == "unchanged":
                tm.that(journal.exists(), eq=False)
                tm.that(target.exists(), eq=False)
            else:
                tm.that(
                    tm.ok(u.Cli.atomic_read_binary_file_state(journal, required=False)),
                    eq=foreign,
                )
                tm.that(
                    tm.ok(u.Cli.atomic_read_binary_file_state(target, required=True)),
                    eq=before,
                )
            return r[bool].ok(True)

        tm.ok(owner.run_files_locked(roots, fail_session))
