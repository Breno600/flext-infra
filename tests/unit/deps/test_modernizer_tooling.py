"""Tooling phase tests for deps modernizer."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import FlextInfraEnsureRuffConfigPhase
from tests import t, u

if TYPE_CHECKING:
    from pathlib import Path

    from tests import m


class TestsFlextInfraDepsModernizerTooling:
    """Declarative tests for the Ruff phase and analyzer surface policy."""

    @staticmethod
    def _project_with_local_ruff_policy(tmp_path: Path, name: str) -> Path:
        """Create one project whose local config extends Ruff per-file ignores."""
        project_dir = tmp_path / name
        config_dir = project_dir / "config"
        config_dir.mkdir(parents=True)
        (config_dir / "cli.yaml").write_text(
            "ManagedArtifacts:\n"
            "  Ruff:\n"
            "    per_file_ignores:\n"
            "      src/flext_cli/_config.py: [N802]\n",
            encoding="utf-8",
        )
        return project_dir

    @staticmethod
    def _applied(
        tool_config_document: m.Infra.ToolConfigDocument,
        project_dir: Path,
        source: str = "",
    ) -> t.Pair[t.MutableJsonMapping, t.JsonMapping]:
        """Apply the Ruff phase twice to one named payload; return payload and ruff."""
        payload = t.Infra.MUTABLE_INFRA_MAPPING_ADAPTER.validate_python(
            u.Tests.toml_payload(f'[project]\nname = "{project_dir.name}"\n{source}')
        )
        phase = FlextInfraEnsureRuffConfigPhase(tool_config_document)
        path = project_dir / "pyproject.toml"
        _ = phase.apply_payload(payload, path=path)
        tm.that(phase.apply_payload(payload, path=path), empty=True)
        return payload, u.Tests.toml_mapping(
            u.Tests.toml_mapping(payload["tool"])["ruff"]
        )

    def test_typecheck_policy_keeps_tracked_surfaces_visible(
        self, tool_config_document: m.Infra.ToolConfigDocument
    ) -> None:
        """Keep every tracked Python surface visible to all four analyzers."""
        tools = tool_config_document.tools
        tracked_surfaces = frozenset({"examples", "scripts", "src", "tests"})
        hidden_globs = frozenset({
            "**/examples",
            "**/examples/**",
            "**/tests",
            "**/tests/**",
        })

        tm.that(frozenset(tools.ruff.src), eq=tracked_surfaces)
        tm.that(
            frozenset(tools.ruff.namespace_packages),
            eq=frozenset({"examples", "scripts", "tests"}),
        )
        tm.that(tracked_surfaces.isdisjoint(tools.ruff.exclude), eq=True)
        # mypy's exclude is config-owned (tooling.yaml) and may legitimately
        # hide non-tracked trees (e.g. legacy sources); the contract is that
        # no exclude pattern ever matches a tracked surface.
        for pattern in tools.mypy.exclude.split(","):
            if pattern:
                tm.that(
                    any(re.match(pattern, surface) for surface in tracked_surfaces),
                    eq=False,
                )
        tm.that(frozenset(tools.pyright.path_rules.env_dirs), eq=tracked_surfaces)
        tm.that(
            hidden_globs.isdisjoint(tools.pyright.path_rules.default_excludes), eq=True
        )
        tm.that(frozenset(tools.pyrefly.path_rules.env_dirs), eq=tracked_surfaces)
        tm.that(hidden_globs.isdisjoint(tools.pyrefly.project_exclude_globs), eq=True)

    def test_ruff_phase_sets_expected_state(
        self, tmp_path: Path, tool_config_document: m.Infra.ToolConfigDocument
    ) -> None:
        """Render Ruff policy, drop stale sections, and converge on second apply."""
        ruff_policy = tool_config_document.tools.ruff
        project_dir = tmp_path / "flext-sample"
        (project_dir / "src" / "flext_sample").mkdir(parents=True)
        (project_dir / "src" / "flext_sample" / "__init__.py").write_text(
            "", encoding="utf-8"
        )
        stale_pattern = "stale-pattern.py"

        payload, ruff = self._applied(
            tool_config_document,
            project_dir,
            '[lint]\nselect = ["E501"]\n'
            f'[tool.ruff.lint.per-file-ignores]\n"{stale_pattern}" = ["E402"]\n',
        )

        tm.that(payload, lacks="lint")
        tm.that(
            frozenset(u.Tests.toml_strings(ruff["exclude"])),
            eq=frozenset(ruff_policy.exclude),
        )
        tm.that(ruff["line-length"], eq=ruff_policy.line_length)
        tm.that(ruff["target-version"], eq=ruff_policy.target_version)
        tm.that(
            frozenset(u.Tests.toml_strings(ruff["src"])), eq=frozenset(ruff_policy.src)
        )
        tm.that(
            u.Tests.toml_mapping(ruff["format"])["docstring-code-format"],
            eq=ruff_policy.format.docstring_code_format,
        )
        lint = u.Tests.toml_mapping(ruff["lint"])
        tm.that(
            frozenset(u.Tests.toml_strings(lint["ignore"])),
            eq=frozenset({
                *ruff_policy.lint.ignore,
                *ruff_policy.lint.ignored_rule_rationales,
            }),
        )
        tm.that(
            list(
                u.Tests.toml_strings(
                    u.Tests.toml_mapping(lint["isort"])["known-first-party"]
                )
            ),
            eq=sorted({
                *tool_config_document.tools.deptry.known_first_party,
                "flext_sample",
            }),
        )
        tm.that(
            u.Tests.toml_mapping(lint["per-file-ignores"]),
            eq={
                pattern: sorted(rules)
                for pattern, rules in ruff_policy.lint.per_file_ignores.items()
            },
        )

    @pytest.mark.parametrize("with_local_policy", [True, False])
    def test_ruff_phase_applies_only_own_project_overrides(
        self,
        tmp_path: Path,
        tool_config_document: m.Infra.ToolConfigDocument,
        *,
        with_local_policy: bool,
    ) -> None:
        """Project config extends Ruff policy only for its own managed artifact."""
        project_dir = (
            self._project_with_local_ruff_policy(tmp_path, "flext-cli")
            if with_local_policy
            else tmp_path / "flext-tests"
        )
        project_dir.mkdir(parents=True, exist_ok=True)

        _, ruff = self._applied(tool_config_document, project_dir)

        ignores = u.Tests.toml_mapping(
            u.Tests.toml_mapping(ruff["lint"])["per-file-ignores"]
        )
        if with_local_policy:
            tm.that(
                list(u.Tests.toml_strings(ignores["src/flext_cli/_config.py"])),
                eq=["N802"],
            )
        else:
            tm.that(ignores, lacks="src/flext_cli/_config.py")

    def test_ruff_phase_skips_nonmember_workspace_namespaces(
        self, tmp_path: Path, tool_config_document: m.Infra.ToolConfigDocument
    ) -> None:
        """Exclude nonmember consumer namespaces from FLEXT first-party names."""
        repository_root = tmp_path / "workspace"
        project_dir = repository_root / "demo-migration-tool"
        internal_project = repository_root / "flext-core"
        (project_dir / "src" / "demo_migration_tool").mkdir(parents=True)
        (internal_project / "src" / "flext_core").mkdir(parents=True)
        for package in (
            project_dir / "src" / "demo_migration_tool",
            internal_project / "src" / "flext_core",
        ):
            (package / "__init__.py").write_text("", encoding="utf-8")
        (project_dir / "pyproject.toml").write_text(
            '[project]\nname = "demo-migration-tool"\nversion = "0.1.0"\n'
            'dependencies = ["flext-core>=0.1.0"]\n',
            encoding="utf-8",
        )
        (repository_root / "pyproject.toml").write_text(
            "[project]\nname = 'workspace'\nversion = '0.1.0'\n\n"
            "[tool.uv.workspace]\nmembers = ['flext-core']\n",
            encoding="utf-8",
        )
        (internal_project / "pyproject.toml").write_text(
            '[project]\nname = "flext-core"\nversion = "0.1.0"\n', encoding="utf-8"
        )

        _, ruff = self._applied(
            tool_config_document,
            repository_root,
            'dependencies = ["flext-core>=0.1.0"]\n',
        )

        known_first_party = u.Tests.toml_strings(
            u.Tests.toml_mapping(u.Tests.toml_mapping(ruff["lint"])["isort"])[
                "known-first-party"
            ]
        )
        tm.that(known_first_party, has="flext_core")
        tm.that(known_first_party, lacks="demo_migration_tool")
