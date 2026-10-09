"""Candidate bootstrap campaigns through the public Infra facade.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, infra, m
from tests import u


class TestsFlextInfraCodegenCandidateBootstrap:
    """A declared campaign publishes all recovery projections or none."""

    @staticmethod
    def _campaign(tmp_path: Path) -> tuple[Path, Path, Path]:
        source, _ = u.Tests.render_make_environment(
            tmp_path / "source",
            c.Infra.MakeProfile.STANDALONE,
        )
        first, _ = u.Tests.render_make_environment(
            tmp_path / "first",
            c.Infra.MakeProfile.STANDALONE,
        )
        second, _ = u.Tests.render_make_environment(
            tmp_path / "second",
            c.Infra.MakeProfile.STANDALONE,
        )
        for root in (first, second):
            u.Tests.write_workspace_manifest(root, root.name)
        manifest = u.Tests.write_workspace_manifest(source, source.name)
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

    @staticmethod
    def test_empty_campaign_fails_loud(tmp_path: Path) -> None:
        """An empty typed list cannot produce a green no-op bootstrap."""
        project_root, _ = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )
        manifest = u.Tests.write_workspace_manifest(
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

    # Real conform transactions over a fixture repository (several full plans
    # per case): integration-scale, so it runs in the slow phase under its
    # per-item bound (rules/workflow/gate-budget.md), never a raised limit.
    @pytest.mark.slow
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
        u.Tests.write_workspace_manifest(second, second.name)
        tm.ok(
            infra.bootstrap_candidate(
                m.Infra.CandidateBootstrapCommand(repository_root=source),
            ),
        )

    @pytest.mark.slow
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

    @pytest.mark.slow
    def test_makefile_bootstrap_does_not_parse_corrupt_tooling(
        self,
        tmp_path: Path,
    ) -> None:
        """Declared topology repairs Make even when a tooling projection is corrupt."""
        source, first, _ = self._campaign(tmp_path)
        pyproject = first / c.PYPROJECT_FILENAME
        content = pyproject.read_text(encoding="utf-8")
        pyproject.write_text(
            content + '\n[tool.mypy]\nplugins = ["pydantic.mypy"]\n',
            encoding="utf-8",
        )
        before = tm.ok(u.Cli.atomic_read_binary_file_state(pyproject, required=True))
        makefile = first / c.Infra.MAKEFILE_FILENAME
        makefile.write_text("ifdef broken\n", encoding="utf-8")

        tm.ok(
            infra.bootstrap_candidate(
                m.Infra.CandidateBootstrapCommand(repository_root=source),
            ),
        )

        tm.that(makefile.read_text(encoding="utf-8"), lacks="ifdef broken")
        tm.that(
            tm.ok(u.Cli.atomic_read_binary_file_state(pyproject, required=True)),
            eq=before,
        )

    @pytest.mark.slow
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

    @staticmethod
    @pytest.mark.slow
    def test_docs_config_conflict_recovers_from_declared_template(
        tmp_path: Path,
    ) -> None:
        """A conflicted docs projection is repaired before generation parses.

        Renders two real Make environments and runs two real bootstraps,
        like its slow-phase sibling below: alone it takes ~9s of the 10s
        bounded-phase item budget, so it belongs to the declared slow phase.
        """
        source, _ = u.Tests.render_make_environment(
            tmp_path / "source",
            c.Infra.MakeProfile.STANDALONE,
        )
        candidate, _ = u.Tests.render_make_environment(
            tmp_path / "candidate",
            c.Infra.MakeProfile.STANDALONE,
        )
        manifest = u.Tests.write_workspace_manifest(source, source.name)
        u.Tests.write_workspace_manifest(candidate, candidate.name)
        manifest.write_text(
            manifest.read_text(encoding="utf-8")
            + "\ncandidate_bootstrap_targets:\n"
            + f"  - path: {Path(os.path.relpath(candidate, source)).as_posix()}\n"
            + "    what: docs-config\n",
            encoding="utf-8",
        )
        projection = candidate / c.Infra.DIR_DOCS / c.Infra.DOCS_CONFIG_FILENAME
        tm.ok(u.Cli.ensure_dir(projection.parent))
        tm.ok(u.Cli.atomic_write_text_file(projection, "<<<<<<< HEAD\n"))
        command = m.Infra.CandidateBootstrapCommand(repository_root=source)

        tm.ok(infra.bootstrap_candidate(command))
        first = tm.ok(u.Cli.atomic_read_binary_file_state(projection, required=True))
        tm.ok(u.Cli.json_loads(first.content or b""))
        tm.ok(infra.bootstrap_candidate(command))
        tm.that(
            tm.ok(u.Cli.atomic_read_binary_file_state(projection, required=True)),
            eq=first,
        )

    @staticmethod
    @pytest.mark.slow
    def test_pyproject_bootstrap_uses_declared_candidate_surface(
        tmp_path: Path,
    ) -> None:
        """A healthy provider restores a candidate before its own Make can import."""
        source, _ = u.Tests.render_make_environment(
            tmp_path / "source",
            c.Infra.MakeProfile.STANDALONE,
        )
        candidate, _ = u.Tests.render_make_environment(
            tmp_path / "candidate",
            c.Infra.MakeProfile.STANDALONE,
        )
        manifest = u.Tests.write_workspace_manifest(source, source.name)
        u.Tests.write_workspace_manifest(candidate, candidate.name)
        manifest.write_text(
            manifest.read_text(encoding="utf-8")
            + "\ncandidate_bootstrap_targets:\n"
            + f"  - path: {Path(os.path.relpath(candidate, source)).as_posix()}\n"
            + "    what: pyproject\n",
            encoding="utf-8",
        )
        projection = candidate / c.PYPROJECT_FILENAME
        tm.ok(
            u.Cli.atomic_write_text_file(
                projection,
                projection.read_text(encoding="utf-8") + "\n# stale projection\n",
            ),
        )
        command = m.Infra.CandidateBootstrapCommand(repository_root=source)

        tm.ok(infra.bootstrap_candidate(command))
        first = tm.ok(u.Cli.atomic_read_binary_file_state(projection, required=True))
        tm.that(
            u.Cli.toml_mapping_from_text((first.content or b"").decode("utf-8"))
            is not None,
            eq=True,
        )
        tm.that(first.content or b"", lacks=b"# stale projection")
        tm.ok(infra.bootstrap_candidate(command))
        tm.that(
            tm.ok(u.Cli.atomic_read_binary_file_state(projection, required=True)),
            eq=first,
        )
