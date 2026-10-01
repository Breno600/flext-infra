"""Project-owned Mise tools: declaration, composition, and lock platform scope."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config, m
from tests import u


class TestsFlextInfraProjectMiseTools:
    """A project declares its own tools without touching the fleet catalog."""

    @staticmethod
    def _project(root: Path, tools_yaml: str) -> Path:
        root.mkdir(parents=True)
        (root / "config").mkdir()
        (root / "config" / "managed-artifacts.yaml").write_text(
            tools_yaml, encoding="utf-8"
        )
        return root

    def test_declared_tool_reaches_generated_mise_toml(self, tmp_path: Path) -> None:
        root = self._project(
            tmp_path / "project",
            "ManagedArtifacts:\n"
            "  Mise:\n"
            "    tools:\n"
            '      "github:example/tool":\n'
            '        version: "1.2.3"\n',
        )

        snapshot = tm.ok(u.Infra.snapshot_project_managed_artifacts(root))
        python_version = config.Infra.codegen.toolchain.python_version
        composed = u.Infra.compose_mise_toml_from_snapshot(
            snapshot.sources, f'[tools]\npython = "{python_version}"\n'
        )

        tools = u.Tests.toml_table_at(tm.ok(composed), "tools")
        assert tools["github:example/tool"] == "1.2.3"
        assert tools["python"] == python_version

    def test_version_string_shorthand_is_not_a_declaration(
        self, tmp_path: Path
    ) -> None:
        root = self._project(
            tmp_path / "project",
            "ManagedArtifacts:\n"
            "  Mise:\n"
            "    tools:\n"
            '      "github:example/tool": "1.2.3"\n',
        )

        with pytest.raises(m.ValidationError):
            u.Infra.load_project_managed_artifacts(root)
