"""Workspace fleet-gaps: one typed hygiene row per declared repository.

Every case drives the public ``workspace fleet-gaps`` CLI over a real
governed workspace: a superproject with one attached member gitlink, a
declared external consumer whose checkout is absent, and a recording
``gh`` on PATH instead of GitHub.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import main
from flext_infra.check import FlextInfraWorkspaceChecker
from tests import c, m, t, u

if TYPE_CHECKING:
    from collections.abc import Generator


class TestsFlextInfraWorkspaceFleetGaps:
    """Behavior contract for the ``workspace fleet-gaps`` verb."""

    MEMBER = "sample-member"

    @staticmethod
    def _member_facts(member: Path) -> None:
        """Seed one member with the facts the report must observe.

        The standards files and the member's own published reports are
        committed first, so the checkout's only uncommitted change is the one
        stray file the porcelain column must name. An unmerged lane branch
        leaves the integration line.
        """
        tm.ok(
            u.Cli.atomic_write_text_file(
                member / c.Infra.AGENTS_DOC_FILENAME,
                "# Member law\n",
            ),
        )
        tm.ok(
            u.Cli.atomic_write_text_file(
                member / c.Infra.SKILLS_STAMP_RELPATH,
                '{"distribution_version": "0.5.0"}\n',
            ),
        )
        tm.ok(
            u.Cli.atomic_write_text_file(
                member / c.Infra.BEADS_RUNTIME_CONFIG_RELPATH,
                "version: 1\n",
            ),
        )
        tm.ok(
            u.Cli.atomic_write_text_file(
                member / c.Infra.MOD_SCAN_REPORT_RELATIVE_PATH,
                '{"findings": 7}\n',
            ),
        )
        u.Tests.commit_git_changes(member, "commit published facts")
        u.Tests.checkout_integration(member)
        tm.ok(
            u.Cli.run_checked(
                [c.Infra.GIT, "switch", "--create", "lane/unmerged"],
                cwd=member,
            ),
        )
        (member / "lane.txt").write_text("lane\n", encoding="utf-8")
        u.Tests.commit_git_changes(member, "unmerged lane work")
        u.Tests.checkout_integration(member)
        (member / "stray.txt").write_text("wip\n", encoding="utf-8")

    @staticmethod
    def _declare_absent_consumer(root: Path, consumer_root: Path) -> None:
        """Declare one external consumer whose checkout does not exist."""
        manifest = root / "config" / c.Infra.WORKSPACE_MANIFEST_FILENAME
        loaded = tm.ok(u.Cli.config_load(manifest, expand_env=False))
        merged: t.JsonDict = dict(loaded.data)
        merged["external_consumers"] = [
            {"name": "consumer-x", "root": str(consumer_root)},
        ]
        tm.ok(u.Cli.yaml_dump(manifest, merged))

    @staticmethod
    def _recording_gh(bin_dir: Path, script: str) -> Path:
        """Install a ``gh`` shim that records instead of reaching GitHub.

        Returns:
            The resulting ``Path``.

        """
        bin_dir.mkdir(parents=True, exist_ok=True)
        log = bin_dir / f"{c.Infra.GH}.log"
        shim = bin_dir / c.Infra.GH
        shim.write_text(f"#!/bin/sh\n{script.format(log=log)}", encoding="utf-8")
        shim.chmod(0o755)
        return log

    @contextmanager
    def _gh_on_path(
        self,
        tmp_path: Path,
        script: str,
    ) -> Generator[Path]:
        """Run the body with the recording shim first on ``PATH``.

        Yields:
            The shim's invocation log path.

        """
        log = self._recording_gh(tmp_path / "bin", script)
        shim_path = f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}"
        with u.Tests.env_vars_context(env_vars={"PATH": shim_path}):
            yield log

    @staticmethod
    def _fleet_gaps(root: Path, *receipts: Path) -> int:
        """Run the public fleet-gaps CLI once.

        Returns:
            The resulting ``int``.

        """
        return main([
            c.Infra.CLI_GROUP_WORKSPACE,
            c.Infra.FLEET_GAPS_ROUTE_NAME,
            "--repository-root",
            str(root),
            *(
                ("--quality-receipts", ",".join(str(path) for path in receipts))
                if receipts
                else ()
            ),
        ])

    @staticmethod
    def _receipt(root: Path) -> m.Infra.FleetGapsReport:
        """Load the typed receipt the verb publishes.

        Returns:
            The resulting ``m.Infra.FleetGapsReport``.

        """
        path = root / c.Infra.FLEET_GAPS_REPORT_RELATIVE_PATH
        return m.Infra.FleetGapsReport.model_validate_json(
            path.read_bytes(),
        )

    def test_report_observes_every_declared_repository(
        self,
        tmp_path: Path,
    ) -> None:
        """One row per member and external consumer, from each repo's facts."""
        root = tmp_path / "workspace"
        member = u.Tests.WorktreeFixture.governed_workspace_with_member(
            root,
            member=self.MEMBER,
        )
        self._member_facts(member)
        self._declare_absent_consumer(root, tmp_path / "consumer-missing")
        with self._gh_on_path(
            tmp_path,
            'printf "%s\\n" "$*" >> "{log}"\n',
        ):
            tm.that(self._fleet_gaps(root), eq=0)

        report = self._receipt(root)
        tm.that(
            report.schema_version,
            eq=c.Infra.FLEET_GAPS_REPORT_SCHEMA_VERSION,
        )
        member_row = next(row for row in report.repos if row.name == self.MEMBER)
        consumer_row = next(row for row in report.repos if row.name == "consumer-x")
        tm.that(member_row.present, eq=True)
        tm.that(member_row.dirty_paths, eq=("stray.txt",))
        tm.that(member_row.unmerged_branches, eq=1)
        tm.that(member_row.lint_findings, eq=None)
        tm.that(member_row.pyrefly_findings, eq=None)
        tm.that(member_row.codemod_findings, eq=7)
        tm.that(member_row.agents_doc_present, eq=True)
        tm.that(member_row.skills_stamp_present, eq=True)
        tm.that(
            member_row.skills_stamp_distribution_version,
            eq="0.5.0",
        )
        tm.that(member_row.beads_config_present, eq=True)
        tm.that(member_row.open_pull_requests, eq=())
        tm.that(consumer_row.present, eq=False)
        tm.that(consumer_row.dirty_paths, eq=())
        tm.that(consumer_row.unmerged_branches, eq=0)
        tm.that(consumer_row.lint_findings, eq=None)
        tm.that(consumer_row.pyrefly_findings, eq=None)
        tm.that(consumer_row.codemod_findings, eq=0)
        tm.that(consumer_row.agents_doc_present, eq=False)
        tm.that(consumer_row.skills_stamp_present, eq=False)
        tm.that(consumer_row.beads_config_present, eq=False)
        gh_log = tmp_path / "bin" / f"{c.Infra.GH}.log"
        tm.that(gh_log.read_text(encoding="utf-8"), has="pr list")

    def test_rerun_over_unchanged_tree_republishes_identical_receipt(
        self,
        tmp_path: Path,
    ) -> None:
        """The verb is its own idempotence proof over an unchanged tree."""
        root = tmp_path / "workspace"
        member = u.Tests.WorktreeFixture.governed_workspace_with_member(
            root,
            member=self.MEMBER,
        )
        self._member_facts(member)
        receipt_path = root / c.Infra.FLEET_GAPS_REPORT_RELATIVE_PATH
        with self._gh_on_path(
            tmp_path,
            'printf "%s\\n" "$*" >> "{log}"\nexit 0\n',
        ):
            tm.that(self._fleet_gaps(root), eq=0)
            first = receipt_path.read_bytes()

            tm.that(self._fleet_gaps(root), eq=0)

        tm.that(receipt_path.read_bytes(), eq=first)

    def test_failing_gh_degrades_to_empty_pull_requests(
        self,
        tmp_path: Path,
    ) -> None:
        """An unreachable provider leaves the row complete and the verb green."""
        root = tmp_path / "workspace"
        member = u.Tests.WorktreeFixture.governed_workspace_with_member(
            root,
            member=self.MEMBER,
        )
        self._member_facts(member)
        with self._gh_on_path(tmp_path, "exit 1\n"):
            tm.that(self._fleet_gaps(root), eq=0)

        member_row = next(
            row for row in self._receipt(root).repos if row.name == self.MEMBER
        )
        tm.that(member_row.open_pull_requests, eq=())
        tm.that(member_row.dirty_paths, eq=("stray.txt",))

    @staticmethod
    def _quality_receipt(
        member: Path,
        reports: Path,
        gates: t.StrSequence,
    ) -> tuple[Path, m.Infra.ProjectResult]:
        """Publish a real checker invocation and return its exact native receipt.

        Returns:
            The published SARIF path and the executed project facts.
        """
        tm.ok(
            u.Cli.atomic_write_text_file(
                member / "src" / "sample.py",
                '"""Sample quality consumer.\n\n'
                "Copyright (c) 2026 FLEXT Team. All rights reserved.\n"
                'SPDX-License-Identifier: MIT\n"""\n',
            )
        )
        results = tm.ok(
            FlextInfraWorkspaceChecker(repository_root=member).run_projects(
                (m.Infra.CheckProjectTarget(name=member.name, path=member),),
                gates,
                reports_dir=reports,
                fail_fast=False,
            )
        )
        (project,) = results
        execution = project.gates[gates[0]]
        native = execution.raw_receipt
        assert native is not None
        return native.parent.parent / c.Infra.CHECK_REPORT_SARIF_FILENAME, project

    def test_explicit_invocation_counts_only_its_own_executed_gates(
        self,
        tmp_path: Path,
    ) -> None:
        """Exact receipt selection survives another invocation under the same base."""
        root = tmp_path / "workspace"
        member = u.Tests.WorktreeFixture.governed_workspace_with_member(
            root, member=self.MEMBER
        )
        pyproject = member / c.PYPROJECT_FILENAME
        tm.ok(
            u.Cli.atomic_write_text_file(
                pyproject,
                pyproject.read_text(encoding=c.Cli.ENCODING_DEFAULT)
                + "\n[tool.pyrefly]\n",
            )
        )
        selected, project = self._quality_receipt(
            member, tmp_path / "quality", (c.Infra.LINT, c.Infra.PYREFLY)
        )
        other, _ = self._quality_receipt(member, tmp_path / "quality", (c.Infra.LINT,))
        tm.that(other, ne=selected)
        with self._gh_on_path(tmp_path, "exit 0\n"):
            tm.that(self._fleet_gaps(root, selected), eq=0)
        row = next(row for row in self._receipt(root).repos if row.name == self.MEMBER)
        tm.that(row.lint_findings, eq=project.gates[c.Infra.LINT].finding_count)
        tm.that(row.pyrefly_findings, eq=project.gates[c.Infra.PYREFLY].finding_count)

    def test_missing_gate_stays_unknown_and_duplicate_receipts_fail(
        self,
        tmp_path: Path,
    ) -> None:
        """A lint invocation cannot invent Pyrefly or aggregate another lint run."""
        root = tmp_path / "workspace"
        member = u.Tests.WorktreeFixture.governed_workspace_with_member(
            root, member=self.MEMBER
        )
        selected, project = self._quality_receipt(
            member, tmp_path / "quality", (c.Infra.LINT,)
        )
        with self._gh_on_path(tmp_path, "exit 0\n"):
            tm.that(self._fleet_gaps(root, selected), eq=0)
            row = next(
                row for row in self._receipt(root).repos if row.name == self.MEMBER
            )
            tm.that(row.lint_findings, eq=project.gates[c.Infra.LINT].finding_count)
            tm.that(row.pyrefly_findings, eq=None)
            before = (root / c.Infra.FLEET_GAPS_REPORT_RELATIVE_PATH).read_bytes()
            tm.that(self._fleet_gaps(root, selected, selected), ne=0)
            tm.that(
                (root / c.Infra.FLEET_GAPS_REPORT_RELATIVE_PATH).read_bytes(), eq=before
            )

    def test_invalid_selected_receipts_never_publish_green_quality(
        self,
        tmp_path: Path,
    ) -> None:
        """Missing, malformed, foreign and missing-native evidence fail causally."""
        root = tmp_path / "workspace"
        member = u.Tests.WorktreeFixture.governed_workspace_with_member(
            root, member=self.MEMBER
        )
        selected, project = self._quality_receipt(
            member, tmp_path / "quality", (c.Infra.LINT,)
        )
        malformed = tmp_path / "malformed.sarif"
        tm.ok(u.Cli.atomic_write_text_file(malformed, "{"))
        foreign = u.Tests.WorktreeFixture.self_named_project(
            tmp_path / "foreign", "foreign"
        )
        unrelated, _ = self._quality_receipt(
            foreign, tmp_path / "foreign-quality", (c.Infra.LINT,)
        )
        with self._gh_on_path(tmp_path, "exit 0\n"):
            for invalid in (tmp_path / "missing.sarif", malformed, unrelated):
                tm.that(self._fleet_gaps(root, invalid), ne=0)
                tm.that(
                    (root / c.Infra.FLEET_GAPS_REPORT_RELATIVE_PATH).exists(), eq=False
                )
            native = project.gates[c.Infra.LINT].raw_receipt
            assert native is not None
            native.unlink()
            tm.that(self._fleet_gaps(root, selected), ne=0)
            tm.that((root / c.Infra.FLEET_GAPS_REPORT_RELATIVE_PATH).exists(), eq=False)

    def test_unexecuted_gates_remain_unknown_in_selected_receipt(
        self,
        tmp_path: Path,
    ) -> None:
        """Real lint findings stop the serial invocation before Pyrefly executes."""
        root = tmp_path / "workspace"
        member = u.Tests.WorktreeFixture.governed_workspace_with_member(
            root, member=self.MEMBER
        )
        tm.ok(
            u.Cli.atomic_write_text_file(
                member / "src" / "sample.py", "import os\nimport os\n"
            )
        )
        reports = tmp_path / "quality"
        results = tm.ok(
            FlextInfraWorkspaceChecker(repository_root=member).run_projects(
                (m.Infra.CheckProjectTarget(name=member.name, path=member),),
                (c.Infra.LINT, c.Infra.PYREFLY),
                reports_dir=reports,
                fail_fast=True,
            )
        )
        (project,) = results
        tm.that(tuple(project.gates), eq=(c.Infra.LINT,))
        lint = project.gates[c.Infra.LINT]
        tm.that(lint.result.passed, eq=False)
        tm.that(lint.outcome, eq=c.Infra.ToolOutcome.FINDINGS)
        tm.that(lint.issues, empty=False)
        native = lint.raw_receipt
        assert native is not None
        selected = native.parent.parent / c.Infra.CHECK_REPORT_SARIF_FILENAME
        with self._gh_on_path(tmp_path, "exit 0\n"):
            tm.that(self._fleet_gaps(root, selected), eq=0)
        row = next(row for row in self._receipt(root).repos if row.name == self.MEMBER)
        tm.that(row.lint_findings, eq=lint.finding_count)
        tm.that(row.pyrefly_findings, eq=None)

    def test_failed_native_verdict_is_not_a_quality_count(
        self,
        tmp_path: Path,
    ) -> None:
        """Corrupting a real receipt's native verdict must fail, not publish zero."""
        root = tmp_path / "workspace"
        member = u.Tests.WorktreeFixture.governed_workspace_with_member(
            root, member=self.MEMBER
        )
        selected, project = self._quality_receipt(
            member, tmp_path / "quality", (c.Infra.LINT,)
        )
        report = m.Infra.SarifReport.model_validate_json(selected.read_bytes())
        summary = report.properties
        assert summary is not None
        execution = project.gates[c.Infra.LINT].model_copy(
            update={"outcome": c.Infra.ToolOutcome.ERROR}
        )
        invalid_project = project.model_copy(
            update={"gates": {c.Infra.LINT: execution}}
        )
        invalid_report = report.model_copy(
            update={
                "properties": summary.model_copy(update={"results": (invalid_project,)})
            }
        )
        tm.ok(
            u.Cli.atomic_write_text_file(
                selected, invalid_report.model_dump_json(round_trip=True)
            )
        )
        with self._gh_on_path(tmp_path, "exit 0\n"):
            tm.that(self._fleet_gaps(root, selected), ne=0)
        tm.that((root / c.Infra.FLEET_GAPS_REPORT_RELATIVE_PATH).exists(), eq=False)

    def test_file_scoped_receipt_never_claims_full_project_quality(
        self,
        tmp_path: Path,
    ) -> None:
        """A public file-gate receipt stays selected; its fleet count is unknown."""
        root = tmp_path / "workspace"
        member = u.Tests.WorktreeFixture.governed_workspace_with_member(
            root, member=self.MEMBER
        )
        source = Path("src/sample.py")
        tm.ok(u.Cli.atomic_write_text_file(member / source, '"""Sample."""\n'))
        reports = tmp_path / "quality"
        checker = FlextInfraWorkspaceChecker(repository_root=member)
        _ = checker.execute_payload(
            m.Infra.RunCommand(
                repository_root=member,
                gates=(c.Infra.LINT,),
                file=source.as_posix(),
                reports_dir=str(reports),
            )
        )
        (selected,) = reports.glob(f"*/{c.Infra.CHECK_REPORT_SARIF_FILENAME}")
        with self._gh_on_path(tmp_path, "exit 0\n"):
            tm.that(self._fleet_gaps(root, selected), eq=0)
        row = next(row for row in self._receipt(root).repos if row.name == self.MEMBER)
        tm.that(row.lint_findings, eq=None)
        tm.that(row.pyrefly_findings, eq=None)
