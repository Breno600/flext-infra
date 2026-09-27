"""Tri-environment golden contract for pure generation inputs."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config, m, t
from flext_infra.services.codegen import FlextInfraCodegen
from tests import c, u


class TestsFlextInfraCodegenRenderPurityGolden:
    """Render remains f(SSOT, templates, PINS) across three host shapes."""

    def _project(self, root: Path) -> Path:
        """Materialize one governed fixture repository."""
        project = u.Tests.mk_project(
            root,
            "render-purity",
            pyproject='[project]\nname = "render-purity"\nversion = "0.1.0"\n',
            with_src=True,
        )
        u.Tests.write_project_beads_config(project, "render-purity")
        u.Tests.initialize_git_repo(
            project, origin_url=u.Tests.repository_ref("render-purity").url
        )
        return project

    def _committed_overlay(self, project: Path, body: str) -> None:
        """Commit one project-owned ManagedArtifacts catalog."""
        config_dir = project / c.CONFIG_DIR_NAME
        config_dir.mkdir(exist_ok=True)
        (config_dir / "tooling.yaml").write_text(body, encoding="utf-8")
        u.Tests.git_bootstrap(project, ("add", "config/tooling.yaml"))
        u.Tests.git_bootstrap(
            project, ("commit", "--no-verify", "-m", "commit managed artifacts")
        )

    @pytest.mark.parametrize(
        "environment", ["runner-clean", "host-runtime", "host-concurrent-wip"]
    )
    def test_vscode_settings_are_identical_in_every_environment(
        self, tmp_path: Path, environment: str
    ) -> None:
        """Runtime state and worktree WIP never change VS Code projections."""
        project = self._project(tmp_path / environment)
        codegen = config.Infra.codegen
        expected = {
            "files.exclude": dict(codegen.vscode_files_exclude_map),
            "files.watcherExclude": dict(codegen.vscode_watcher_exclude_map),
            "search.exclude": dict(codegen.vscode_search_exclude_map),
        }
        if environment == "host-runtime":
            runtime = tmp_path / config.Infra.codegen.toolchain.state_directory_name
            runtime.mkdir()
            (runtime / project.name).mkdir()
            (runtime / project.name / "testmondata").touch()
            (project / config.Infra.codegen.toolchain.state_directory_name).mkdir()
        if environment == "host-concurrent-wip":
            (project / "wip_module.py").write_text(
                "def leaked_private_call():\n    return object().__class__\n",
                encoding="utf-8",
            )
            (project / c.CONFIG_DIR_NAME / "wip-tooling.yaml").write_text(
                "ManagedArtifacts:\n  Gitignore:\n    patterns: [wip-artifact/]\n",
                encoding="utf-8",
            )

        rendered: str = tm.ok(FlextInfraCodegen.render_vscode_settings(project))
        parsed: t.JsonValue = tm.ok(u.Cli.json_parse(rendered))
        settings = t.Cli.JSON_MAPPING_ADAPTER.validate_python(parsed)

        for key, value in expected.items():
            tm.that(settings[key], eq=value, msg=f"{environment}: {key}")

    def test_ruff_catalog_reads_committed_head_not_worktree_wip(
        self, tmp_path: Path
    ) -> None:
        """The committed catalog is the sole project Ruff render authority."""
        project = self._project(tmp_path / "catalog")
        self._committed_overlay(
            project,
            "ManagedArtifacts:\n"
            "  Ruff:\n"
            "    per_file_ignores:\n"
            "      tests/**: [S101]\n",
        )
        (project / c.CONFIG_DIR_NAME / "wip-tooling.yaml").write_text(
            "ManagedArtifacts:\n"
            "  Ruff:\n"
            "    per_file_ignores:\n"
            "      src/**: [SLF001]\n",
            encoding="utf-8",
        )

        committed = tm.ok(u.Infra.load_committed_project_managed_artifacts(project))
        working = tm.ok(u.Infra.load_project_managed_artifacts(project))

        tm.that(
            dict(committed.artifacts.Ruff.per_file_ignores), eq={"tests/**": ("S101",)}
        )
        tm.that(
            dict(working.artifacts.Ruff.per_file_ignores),
            eq={"src/**": ("SLF001",), "tests/**": ("S101",)},
        )

    def test_fixture_scaffold_year_is_the_production_ssot(self) -> None:
        """Fixture identity uses the same year declaration production renders."""
        year = config.Infra.codegen.scaffold.project.copyright_year
        spec: m.Infra.ProjectSpec = u.Tests.project_spec("year-owner")

        tm.that(spec.year, eq=year)
