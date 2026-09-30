"""Candidate bootstrap behavior at the public service boundary."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import c
from flext_infra.codegen.candidate_bootstrap import FlextInfraCodegenCandidateBootstrap
from tests import u


class TestsFlextInfraCodegenCandidateBootstrap:
    """A campaign must declare real targets before it can publish anything."""

    def test_empty_campaign_fails_loud(self, tmp_path: Path) -> None:
        """An empty typed list cannot produce a green no-op bootstrap."""
        project_root, _ = u.Tests.render_make_environment(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        manifest = project_root / "config" / "workspace.yaml"
        manifest.write_text(
            manifest.read_text(encoding="utf-8")
            + "\ncandidate_bootstrap_targets: []\n",
            encoding="utf-8",
        )

        result = FlextInfraCodegenCandidateBootstrap(
            repository_root=project_root
        ).execute()

        tm.that(result.failure, eq=True)
        tm.that(result.error, has="candidate bootstrap targets are not declared")
