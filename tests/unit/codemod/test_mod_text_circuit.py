"""Public sed-by-list contract for the ``make mod`` text phase."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_core import r
from flext_infra import c, m, p, u
from flext_infra.codegen import (
    FlextInfraCodegenMiseArtifacts,
    FlextInfraCodegenTransaction,
)
from flext_infra.codemod import FlextInfraModTextGateEngine

if TYPE_CHECKING:
    from flext_infra import t


class TestsFlextInfraModTextGateEngine:
    """Exercise the declarative sed-by-list engine through its public scan."""

    @staticmethod
    def _publication_inputs(root: Path) -> t.Pair[Path, Path]:
        """Declare two authored inputs and one exact text rewrite catalogue."""
        u.Cli.atomic_write_text_file(
            root / c.Infra.CODEMOD_TEXT_RULES_RELPATH,
            "rules:\n  - id: publication-probe\n    find: 'before'\n    replace: 'after'\n",
        ).unwrap()
        package = root / "src" / "mod_workspace"
        u.Cli.ensure_dir(package).unwrap()
        first, second = package / "first.py", package / "second.py"
        for path in (first, second):
            u.Cli.atomic_write_text_file(path, 'value = "before"\n').unwrap()
        return first, second

    def test_generated_destination_rejects_the_entire_text_batch(
        self, mod_workspace: Path
    ) -> None:
        """An authored earlier file stays unchanged when a generator owns a target."""
        first, second = self._publication_inputs(mod_workspace)
        generated = f'{c.Infra.AUTOGEN_HEADERS[0]}\nvalue = "before"\n'
        u.Cli.atomic_write_text_file(second, generated).unwrap()
        original = first.read_bytes()

        scanned = FlextInfraModTextGateEngine.scan(mod_workspace, fix=False).unwrap()
        tm.that(scanned.actionable, eq=2)
        result = FlextInfraModTextGateEngine.scan(mod_workspace, fix=True)

        tm.fail(result, has="canonical generator repair")
        tm.that(first.read_bytes(), eq=original)
        tm.that(second.read_text(encoding="utf-8"), eq=generated)

    def test_invalid_later_source_never_publishes_an_earlier_rewrite(
        self, mod_workspace: Path
    ) -> None:
        """Decoding failure escapes before any file in the prepared batch is written."""
        first, second = self._publication_inputs(mod_workspace)
        second.write_bytes(b"\xff")
        original = first.read_bytes()

        with pytest.raises(UnicodeDecodeError):
            FlextInfraModTextGateEngine.scan(mod_workspace, fix=True)

        tm.that(first.read_bytes(), eq=original)
        tm.that(second.read_bytes(), eq=b"\xff")

    def test_linked_destination_identity_never_publishes_the_batch(
        self, mod_workspace: Path
    ) -> None:
        """A symlink cannot impersonate an authenticated physical destination."""
        first, second = self._publication_inputs(mod_workspace)
        alias = second.with_suffix(".linked")
        second.rename(alias)
        second.symlink_to(alias)
        original = first.read_bytes()

        result = FlextInfraModTextGateEngine.scan(mod_workspace, fix=True)
        tm.fail(result, has="regular file")

        tm.that(first.read_bytes(), eq=original)
        tm.that(second.read_bytes(), eq=original)
        tm.that(alias.read_bytes(), eq=original)

    @pytest.mark.parametrize("raise_failure", [False, True])
    def test_text_phase_validation_failure_recovers_published_files(
        self, mod_workspace: Path, *, raise_failure: bool
    ) -> None:
        """The public transaction owner restores its batch after validator failure."""
        paths = self._publication_inputs(mod_workspace)
        states = tuple(
            u.Cli.atomic_read_binary_file_state(path, required=True).unwrap()
            for path in paths
        )
        plans = tuple(
            m.Infra.CodegenFilePlan(
                project=mod_workspace,
                path=state.path,
                before=state,
                desired_content=b'value = "after"\n',
                desired_mode=state.mode,
                source_states=(state,),
                owner="mod-text",
            )
            for state in states
        )
        analysis = m.Infra.CodegenPhaseAnalysis(
            phase="mod-text", files=plans, inputs=states
        )
        transaction = FlextInfraCodegenTransaction(
            FlextInfraCodegenMiseArtifacts(repository_root=mod_workspace)
        )
        roots = {"@mod-text": mod_workspace}
        failure = RuntimeError("text publication acceptance rejected")

        def reject_published() -> p.Result[bool]:
            for path in paths:
                tm.that(path.read_bytes(), eq=b'value = "after"\n')
            if raise_failure:
                raise failure
            return r[bool].fail("text publication acceptance rejected")

        def publish(scope: Path) -> p.Result[t.VariadicTuple[Path]]:
            session = transaction.begin_files_locked(scope, roots, states).unwrap()

            def apply(
                active: m.Infra.CodegenTransactionSession,
            ) -> p.Result[t.VariadicTuple[Path]]:
                updated = transaction.append_phase_locked(
                    active, analysis.phase, plans
                ).unwrap()
                return transaction.commit_locked(updated, reject_published)

            return transaction.publish_prepared_locked(session, apply)

        if raise_failure:
            with pytest.raises(RuntimeError) as raised:
                transaction.run_files_locked(roots, publish)
            tm.that(raised.value is failure, eq=True)
        else:
            result = transaction.run_files_locked(roots, publish)
            tm.fail(result, has="text publication acceptance rejected")
        for state in states:
            tm.that(state.path.read_bytes(), eq=state.content)
        tm.that(tuple(mod_workspace.rglob("*.semantic-staging")), empty=True)

    def test_scan_proves_rewrite_receipt_and_fixed_point(
        self, mod_workspace: Path
    ) -> None:
        """One list entry rewrites its match once and reaches a fixed point."""
        tm.ok(
            u.Cli.atomic_write_text_file(
                mod_workspace / c.Infra.CODEMOD_TEXT_RULES_RELPATH,
                (
                    "rules:\n"
                    "  - id: rewrite-serialization-lock-call\n"
                    "    description: prove one list-driven rewrite receipt\n"
                    "    find: 'serialization_lock_execute\\(paths, timeout\\)'\n"
                    "    replace: 'serialization_lock_execute(chunks, deadline)'\n"
                    "    expected: 1\n"
                ),
            )
        )
        sample = mod_workspace / "sample.py"
        # Derived, never frozen: the fixture owns the module's shape, so the
        # expected line is read from it (project law P0 — a test never hardcodes
        # a value its own source of truth can produce).
        expected_line = next(
            index
            for index, text in enumerate(
                sample.read_text(encoding="utf-8").splitlines(), start=1
            )
            if "paths, timeout" in text
        )

        first = tm.ok(
            FlextInfraModTextGateEngine.scan(
                mod_workspace, fix=False, validate_receipts=True
            )
        )
        tm.that(first.findings, eq=1)
        tm.that(first.actionable, eq=1)
        tm.that(len(first.files), eq=1)
        finding = first.entries[0]
        tm.that(finding.rule_id, eq="rewrite-serialization-lock-call")
        tm.that(finding.line, eq=expected_line)
        tm.that(sample.read_text(encoding="utf-8").count("paths, timeout"), eq=1)

        applied = tm.ok(FlextInfraModTextGateEngine.scan(mod_workspace, fix=True))
        tm.that(applied.findings, eq=1)
        final = tm.ok(FlextInfraModTextGateEngine.scan(mod_workspace, fix=False))
        tm.that(final.findings, eq=0)
        # This optional migration precondition deliberately does not promise
        # idempotence once the invocation has consumed its exact matches.
        with pytest.raises(
            RuntimeError, match="expected 1 finding\\(s\\), scan produced 0"
        ):
            FlextInfraModTextGateEngine.scan(
                mod_workspace, fix=True, validate_receipts=True
            )
        # The rewrite is proven by what changed, not by freezing the fixture's
        # whole text: the elected call carries the replacement and the original
        # argument list is gone.
        rewritten = sample.read_text(encoding="utf-8")
        tm.that(rewritten, has="serialization_lock_execute(chunks, deadline)")
        tm.that(rewritten, lacks="serialization_lock_execute(paths, timeout)")

    @pytest.mark.parametrize("fix", [False, True])
    def test_scan_requires_declared_receipt_to_match_exactly(
        self, mod_workspace: Path, *, fix: bool
    ) -> None:
        """A wrong expected-count receipt fails the scan loudly."""
        tm.ok(
            u.Cli.atomic_write_text_file(
                mod_workspace / c.Infra.CODEMOD_TEXT_RULES_RELPATH,
                (
                    "rules:\n"
                    "  - id: rewrite-serialization-lock-call\n"
                    "    find: 'serialization_lock_execute\\(paths, timeout\\)'\n"
                    "    replace: 'serialization_lock_execute(chunks, deadline)'\n"
                    "    expected: 2\n"
                ),
            )
        )
        original = (mod_workspace / "sample.py").read_bytes()
        with pytest.raises(RuntimeError, match="expected 2 finding\\(s\\), scan"):
            FlextInfraModTextGateEngine.scan(
                mod_workspace, fix=fix, validate_receipts=True
            )
        tm.that((mod_workspace / "sample.py").read_bytes(), eq=original)

    def test_load_rules_rejects_unknown_keys_and_duplicate_ids(
        self, mod_workspace: Path
    ) -> None:
        """Declarative list entries must be exact and unique."""
        tm.ok(
            u.Cli.atomic_write_text_file(
                mod_workspace / c.Infra.CODEMOD_TEXT_RULES_RELPATH,
                (
                    "rules:\n"
                    "  - id: first\n"
                    "    find: 'alpha'\n"
                    "  - id: second\n"
                    "    find: 'beta'\n"
                    "    unsupported: true\n"
                ),
            )
        )
        unknown = FlextInfraModTextGateEngine.load_rules(mod_workspace)
        tm.that(unknown.failure)
        tm.that("unsupported" in str(unknown.error), eq=True)

        tm.ok(
            u.Cli.atomic_write_text_file(
                mod_workspace / c.Infra.CODEMOD_TEXT_RULES_RELPATH,
                "rules:\n  - id: first\n    find: 'alpha'\n  - id: first\n    find: 'beta'\n",
            )
        )
        duplicate = FlextInfraModTextGateEngine.load_rules(mod_workspace)
        tm.that(duplicate.failure)
        tm.that("duplicate text rule id" in str(duplicate.error), eq=True)

        tm.ok(
            u.Cli.atomic_write_text_file(
                mod_workspace / c.Infra.CODEMOD_TEXT_RULES_RELPATH,
                "rules:\n  - id: first\n    find: 'alpha'\n  - id: second\n    find: 'beta'\n",
            )
        )
        valid = tm.ok(FlextInfraModTextGateEngine.load_rules(mod_workspace))
        tm.that(len(valid), eq=2)

    def test_include_and_exclude_globs_elect_exact_targets(
        self, mod_workspace: Path
    ) -> None:
        """Glob election scopes the rewrite to the declared surfaces only."""
        package_dir = mod_workspace / "src" / "mod_workspace"
        tm.ok(u.Cli.ensure_dir(package_dir))
        tm.ok(
            u.Cli.atomic_write_text_file(
                package_dir / "frozen.py", "LEGACY_PIN = '2026.8.14'\n"
            )
        )
        tm.ok(
            u.Cli.atomic_write_text_file(
                mod_workspace / c.Infra.CODEMOD_TEXT_RULES_RELPATH,
                (
                    "rules:\n"
                    "  - id: rewrite-frozen-pin\n"
                    "    include: ['src/**']\n"
                    "    exclude: ['**/legado/**']\n"
                    "    find: 'LEGACY_PIN = .*'\n"
                    "    replace: 'LEGACY_PIN = values.pin()'\n"
                    "    expected: 1\n"
                ),
            )
        )
        first = tm.ok(
            FlextInfraModTextGateEngine.scan(
                mod_workspace, fix=False, validate_receipts=True
            )
        )
        tm.that(first.findings, eq=1)
        tm.that(first.entries[0].file.as_posix(), eq="src/mod_workspace/frozen.py")

        tm.ok(
            u.Cli.atomic_write_text_file(
                mod_workspace / c.Infra.CODEMOD_TEXT_RULES_RELPATH,
                (
                    "rules:\n"
                    "  - id: rewrite-frozen-pin\n"
                    "    include: ['src/**']\n"
                    "    exclude: ['**/frozen.py']\n"
                    "    find: 'LEGACY_PIN = .*'\n"
                    "    replace: 'LEGACY_PIN = values.pin()'\n"
                    "    expected: 0\n"
                ),
            )
        )
        excluded = tm.ok(
            FlextInfraModTextGateEngine.scan(
                mod_workspace, fix=False, validate_receipts=True
            )
        )
        tm.that(excluded.findings, eq=0)
