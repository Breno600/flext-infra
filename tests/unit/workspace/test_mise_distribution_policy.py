"""Fleet-owned mise tool composition at its owner.

``codegen conform`` exclusively owns ``.mise.toml`` (workspace environment
sync stopped writing it when the toolchain transaction landed), so the
composition rule is proven through the immutable project snapshot and the
public composer that turns that source view into the managed file.
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import config
from tests import u


class TestsFlextInfraMiseDistributionPolicy:
    """Fleet tools win over a project's stale local declaration."""

    @staticmethod
    def _workspace(root: Path) -> Path:
        u.Tests.WorktreeFixture.write_python_project(root, "fixture")
        return root

    def test_managed_artifacts_fleet_wins_over_divergent_pin(
        self, tmp_path: Path
    ) -> None:
        """A project pin diverging from a tool the fleet now owns is residue.

        Resilient composition (operator law 2026-09-18): promoting a project
        tool to the fleet SSOT must never block generation in any consumer.
        The fleet version wins and the stale local declaration is reported
        for removal instead of failing the projection.
        """
        root = self._workspace(tmp_path / "project")
        config_dir = root / "config"
        config_dir.mkdir()
        toolchain = config.Infra.codegen.toolchain
        selector, version = toolchain.qlty_selector, toolchain.qlty_version
        (config_dir / "tools.yaml").write_text(
            "ManagedArtifacts:\n  Mise:\n    tools:\n"
            f'      "{selector}":\n        version: "{version}.divergent"\n',
            encoding="utf-8",
        )

        snapshot = tm.ok(u.Infra.snapshot_project_managed_artifacts(root))
        result = u.Infra.compose_mise_toml_from_snapshot(
            snapshot.sources, f'[tools]\n"{selector}" = "{version}"\n'
        )

        tm.ok(result)
        tm.that(result.value, has=f'"{selector}" = "{version}"')
        tm.that(result.value, lacks="divergent")


__all__: list[str] = ["TestsFlextInfraMiseDistributionPolicy"]
