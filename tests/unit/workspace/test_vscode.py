"""Canonical VS Code settings codegen merge contract tests.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import config
from flext_infra.services import FlextInfraCodegen
from tests import c, u


class TestsFlextInfraCodegenVscode:
    """Behavior contract for the config-driven VS Code settings codegen owner."""

    @staticmethod
    def _write_settings(project_root: Path, content: str) -> Path:
        settings_path = project_root / ".vscode" / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        _ = settings_path.write_text(content, encoding="utf-8")
        return settings_path

    def test_applies_canonical_settings_and_removes_retired_artifacts(
        self,
        tmp_path: Path,
    ) -> None:
        """Enforce canonical keys while deleting stale generated map entries."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        self._write_settings(
            project_root,
            tm.ok(
                u.Cli.json_dumps({
                    "python.languageServer": "None",
                    "python.analysis.typeCheckingMode": "off",
                    "files.exclude": {"**/.retired-cache": True},
                    "python.analysis.diagnosticSeverityOverrides": {
                        "reportUnknownMemberType": "none",
                    },
                }),
            )
            + "\n",
        )

        result = FlextInfraCodegen.render_vscode_settings(project_root)
        tm.ok(result)
        doc = u.Tests.json_payload(result.value)
        tm.that("python.analysis.typeCheckingMode" in doc, eq=False)
        tm.that("python.analysis.diagnosticSeverityOverrides" in doc, eq=False)
        interpreter = "python.defaultInterpreterPath"
        tm.that(
            doc[interpreter],
            eq=config.Infra.codegen.vscode.scalar_settings[interpreter],
        )
        search_paths_key = c.Infra.VSCODE_PYTHON_ENVS_SEARCH_PATHS_KEY
        tm.that(search_paths_key in config.Infra.codegen.vscode.list_settings, eq=False)
        tm.that(search_paths_key in doc, eq=False)
        excludes = u.Tests.toml_mapping(doc["files.exclude"])
        tm.that("**/.retired-cache" in excludes, eq=False)
        tm.that(excludes["**/.mypy_cache"], eq=True)
        tm.that(
            doc["python.languageServer"],
            eq=config.Infra.codegen.vscode.scalar_settings["python.languageServer"],
        )

    def test_strips_retired_keys_owning_pyright_config(self, tmp_path: Path) -> None:
        """Strip keys owned by [tool.pyright] to avoid Pylance warnings."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        self._write_settings(
            project_root,
            tm.ok(
                u.Cli.json_dumps({
                    "python.analysis.typeCheckingMode": "standard",
                    "python.analysis.diagnosticSeverityOverrides": {
                        "reportMissingTypeStubs": "error",
                    },
                    "python.languageServer": "Pylance",
                }),
            )
            + "\n",
        )

        result = FlextInfraCodegen.render_vscode_settings(project_root)

        tm.ok(result)
        doc = u.Tests.json_payload(result.value)
        tm.that("python.analysis.typeCheckingMode" in doc, eq=False)
        tm.that("python.analysis.diagnosticSeverityOverrides" in doc, eq=False)
        tm.that(doc["python.languageServer"], eq="Pylance")

    def test_render_reaches_fixed_point(self, tmp_path: Path) -> None:
        """Rendering a document that was already rendered produces no drift."""
        project_root = tmp_path / "project"
        project_root.mkdir()

        first = FlextInfraCodegen.render_vscode_settings(project_root)
        tm.ok(first)
        self._write_settings(project_root, first.value)
        second = FlextInfraCodegen.render_vscode_settings(project_root)
        tm.ok(second)
        tm.that(second.value, eq=first.value)

    @staticmethod
    def test_python_environment_settings_are_independent_from_repository_topology(
        tmp_path: Path,
    ) -> None:
        """Keep opened-folder settings canonical for roots and subprojects."""
        project_root = tmp_path / "workspace"
        project_root.mkdir()
        provider = u.Tests.provider()
        (project_root / c.Infra.GITMODULES).write_text(
            '[submodule "app-a"]\n'
            "\tpath = apps/a\n"
            f"\turl = {provider.base_url.rstrip('/')}/app-a.git\n"
            f"\tbranch = {u.Tests.provider_branch()}\n"
            '[submodule "lib-b"]\n'
            "\tpath = libs/b\n"
            f"\turl = {provider.base_url.rstrip('/')}/lib-b.git\n"
            f"\tbranch = {u.Tests.provider_branch()}\n",
            encoding="utf-8",
        )

        result = FlextInfraCodegen.render_vscode_settings(project_root)
        standalone_root = tmp_path / "standalone"
        standalone_root.mkdir()
        standalone = FlextInfraCodegen.render_vscode_settings(standalone_root)

        tm.ok(result)
        tm.ok(standalone)
        tm.that(result.value.encode(), eq=standalone.value.encode())
        doc = u.Tests.json_payload(result.value)
        search_paths_key = c.Infra.VSCODE_PYTHON_ENVS_SEARCH_PATHS_KEY
        tm.that(search_paths_key in config.Infra.codegen.vscode.list_settings, eq=False)
        tm.that(search_paths_key in doc, eq=False)

    def test_invalid_json_fails_without_producing_a_document(
        self,
        tmp_path: Path,
    ) -> None:
        """Return a typed failure when the existing settings are unparseable."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        self._write_settings(project_root, "{ invalid json")

        result = FlextInfraCodegen.render_vscode_settings(project_root)

        tm.fail(result)
        tm.that(result.error, none=False)
