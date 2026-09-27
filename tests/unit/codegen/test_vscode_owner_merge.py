"""Owner-merge dispatch for governed .vscode/settings.json artifacts."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import c, config, t, u
from flext_infra.services.codegen import FlextInfraCodegen
from tests import TestsFlextInfraUtilities as test_utilities


class TestsFlextInfraVscodeOwnerMerge:
    """Prove the vscode owner merge renders canonical settings in conform."""

    def test_merge_marks_drift_and_renders_canonical_content(
        self, tmp_path: Path
    ) -> None:
        """Plan a changed merge artifact with canonical and custom keys."""
        root = tmp_path / "project"
        settings_path = root / ".vscode" / "settings.json"
        settings_path.parent.mkdir(parents=True)
        _ = settings_path.write_text(
            '{"python.languageServer": "None"}\n', encoding="utf-8"
        )

        result = FlextInfraCodegen.render_vscode_settings(root)

        tm.ok(result)
        doc = t.Cli.JSON_MAPPING_ADAPTER.validate_python(
            tm.ok(u.Cli.json_parse(result.value))
        )
        for key, expected_value in config.Infra.codegen.vscode.scalar_settings.items():
            tm.that(doc[key], eq=expected_value)
        for stripped in config.Infra.codegen.vscode.stripped_keys:
            tm.that(stripped in doc, eq=False)
        search_paths = t.Cli.JSON_LIST_ADAPTER.validate_python(
            doc[c.Infra.VSCODE_PYTHON_ENVS_SEARCH_PATHS_KEY]
        )
        expected = test_utilities.Tests.vscode_declared_search_paths()
        tm.that(search_paths, eq=expected)
        tm.that("./apps/*/.venv" in search_paths, eq=False)

    def test_merge_reaches_fixed_point_after_apply(self, tmp_path: Path) -> None:
        """Replan a written merge artifact with zero residual drift."""
        root = tmp_path / "project"
        settings_path = root / ".vscode" / "settings.json"
        settings_path.parent.mkdir(parents=True)
        _ = settings_path.write_text("{}\n", encoding="utf-8")
        first = FlextInfraCodegen.render_vscode_settings(root)
        tm.ok(first)
        _ = settings_path.write_text(first.value, encoding="utf-8")

        second = FlextInfraCodegen.render_vscode_settings(root)

        tm.ok(second)
        tm.that(second.value, eq=first.value)

    def test_merge_removes_keys_absent_from_artifact_authority(
        self, tmp_path: Path
    ) -> None:
        """Artifact exclude maps are exact projections, not append-only unions."""
        root = tmp_path / "project"
        settings_path = root / ".vscode" / "settings.json"
        settings_path.parent.mkdir(parents=True)
        stale_key = "**/.retired-runtime"
        _ = settings_path.write_text(
            tm.ok(u.Cli.json_dumps({"files.exclude": {stale_key: True}})),
            encoding="utf-8",
        )

        result = FlextInfraCodegen.render_vscode_settings(root)

        tm.ok(result)
        doc = t.Cli.JSON_MAPPING_ADAPTER.validate_python(
            tm.ok(u.Cli.json_parse(result.value))
        )
        tm.that(
            doc["files.exclude"], eq=dict(config.Infra.codegen.vscode_files_exclude_map)
        )

    def test_merge_strips_retired_pyright_keys(self, tmp_path: Path) -> None:
        """Pylance settingsNotOverridable keys must be stripped, not preserved."""
        root = tmp_path / "project"
        settings_path = root / ".vscode" / "settings.json"
        settings_path.parent.mkdir(parents=True)
        _ = settings_path.write_text(
            tm.ok(
                u.Cli.json_dumps({
                    "python.analysis.typeCheckingMode": "standard",
                    "python.analysis.diagnosticSeverityOverrides": {
                        "reportMissingTypeStubs": "error"
                    },
                })
            ),
            encoding="utf-8",
        )

        result = FlextInfraCodegen.render_vscode_settings(root)

        tm.ok(result)
        doc = t.Cli.JSON_MAPPING_ADAPTER.validate_python(
            tm.ok(u.Cli.json_parse(result.value))
        )
        tm.that("python.analysis.typeCheckingMode" in doc, eq=False)
        tm.that("python.analysis.diagnosticSeverityOverrides" in doc, eq=False)
