"""Candidate bootstrap campaigns through the public Infra facade."""

from __future__ import annotations

import os
from pathlib import Path

from flext_tests import tm

from flext_infra import c, infra, m, u
from tests import u as tests_u


class TestsFlextInfraCodegenCandidateBootstrap:
    """A declared campaign publishes all Makefiles or none."""

    @staticmethod
    def _campaign(tmp_path: Path) -> tuple[Path, Path, Path]:
        source, _ = tests_u.Tests.render_make_environment(
            tmp_path / "source",
            c.Infra.MakeProfile.STANDALONE,
        )
        first, _ = tests_u.Tests.render_make_environment(
            tmp_path / "first",
            c.Infra.MakeProfile.STANDALONE,
        )
        second, _ = tests_u.Tests.render_make_environment(
            tmp_path / "second",
            c.Infra.MakeProfile.STANDALONE,
        )
        for root in (first, second):
            tests_u.Tests.write_workspace_manifest(root, root.name)
        manifest = tests_u.Tests.write_workspace_manifest(source, source.name)
        declaration = "candidate_bootstrap_targets:\n" + "".join(
            f"  - path: {Path(os.path.relpath(root, source)).as_posix()}\n"
            "    what: makefile\n"
            for root in (first, second)
        )
        manifest.write_text(
            manifest.read_text(encoding="utf-8") + "\n" + declaration,
            encoding="utf-8",
        )
        return source, first, second

    def test_empty_campaign_fails_loud(self, tmp_path: Path) -> None:
        """An empty typed list cannot produce a green no-op bootstrap."""
        project_root, _ = tests_u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )
        manifest = tests_u.Tests.write_workspace_manifest(
            project_root,
            "fixture-project",
        )
        manifest.write_text(
            manifest.read_text(encoding="utf-8")
            + "\ncandidate_bootstrap_targets: []\n",
            encoding="utf-8",
        )

        result = infra.bootstrap_candidate(
            m.Infra.CandidateBootstrapCommand(repository_root=project_root),
        )

        tm.that(result.failure, eq=True)
        tm.that(result.error, has="candidate bootstrap targets are not declared")

    def test_invalid_second_target_preserves_first_and_allows_retry(
        self,
        tmp_path: Path,
    ) -> None:
        """Planning must finish for every target before any bytes are published."""
        source, first, second = self._campaign(tmp_path)
        first_makefile = first / c.Infra.MAKEFILE_FILENAME
        first_makefile.write_text("stale candidate Makefile\n", encoding="utf-8")
        before = tm.ok(
            u.Cli.atomic_read_binary_file_state(first_makefile, required=True),
        )
        second_manifest = second / "config" / "workspace.yaml"
        second_manifest.write_text("invalid: [\n", encoding="utf-8")

        failed = infra.bootstrap_candidate(
            m.Infra.CandidateBootstrapCommand(repository_root=source),
        )

        tm.that(failed.failure, eq=True)
        tm.that(
            tm.ok(u.Cli.atomic_read_binary_file_state(first_makefile, required=True)),
            eq=before,
        )
        tests_u.Tests.write_workspace_manifest(second, second.name)
        tm.ok(
            infra.bootstrap_candidate(
                m.Infra.CandidateBootstrapCommand(repository_root=source),
            ),
        )

    def test_two_targets_reach_one_repeatable_fixed_point(self, tmp_path: Path) -> None:
        """A successful campaign publishes both and repeats without drift."""
        source, first, second = self._campaign(tmp_path)
        for root in (first, second):
            (root / c.Infra.MAKEFILE_FILENAME).write_text(
                "stale candidate Makefile\n",
                encoding="utf-8",
            )
        command = m.Infra.CandidateBootstrapCommand(repository_root=source)

        tm.ok(infra.bootstrap_candidate(command))
        committed = tuple(
            tm.ok(
                u.Cli.atomic_read_binary_file_state(
                    root / c.Infra.MAKEFILE_FILENAME,
                    required=True,
                ),
            )
            for root in (first, second)
        )
        tm.ok(infra.bootstrap_candidate(command))
        repeated = tuple(
            tm.ok(
                u.Cli.atomic_read_binary_file_state(
                    root / c.Infra.MAKEFILE_FILENAME,
                    required=True,
                ),
            )
            for root in (first, second)
        )
        tm.that(repeated, eq=committed)
        tm.that(
            all(state.content != b"stale candidate Makefile\n" for state in committed),
            eq=True,
        )

    def test_check_only_reports_drift_without_publication(self, tmp_path: Path) -> None:
        """A check does not enter the recoverable writer or change a target."""
        source, first, _ = self._campaign(tmp_path)
        first_makefile = first / c.Infra.MAKEFILE_FILENAME
        first_makefile.write_text("stale candidate Makefile\n", encoding="utf-8")
        before = tm.ok(
            u.Cli.atomic_read_binary_file_state(first_makefile, required=True),
        )

        result = infra.bootstrap_candidate(
            m.Infra.CandidateBootstrapCommand(repository_root=source, check_only=True),
        )

        tm.that(result.failure, eq=True)
        tm.that(
            tm.ok(u.Cli.atomic_read_binary_file_state(first_makefile, required=True)),
            eq=before,
        )
