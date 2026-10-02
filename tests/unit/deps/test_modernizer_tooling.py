"""Tooling phase tests for deps modernizer.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import FlextInfraEnsureRuffConfigPhase
from tests import m, t, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraDepsModernizerTooling:
    """Declarative tests for the Ruff phase and analyzer surface policy."""

    @staticmethod
    def _applied(
        tool_config_document: m.Infra.ToolConfigDocument,
        project_dir: Path,
        source: str = "",
    ) -> t.Pair[t.MutableJsonMapping, t.JsonMapping]:
        """Apply the Ruff phase twice to one named payload; return payload and ruff.

        Returns:
            The resulting ``t.Pair[t.MutableJsonMapping, t.JsonMapping]``.

        """
        payload = t.Infra.MUTABLE_INFRA_MAPPING_ADAPTER.validate_python(
            u.Tests.toml_payload(f'[project]\nname = "{project_dir.name}"\n{source}'),
        )
        phase = FlextInfraEnsureRuffConfigPhase(tool_config_document)
        path = project_dir / "pyproject.toml"
        _ = phase.apply_payload(payload, path=path)
        tm.that(phase.apply_payload(payload, path=path), empty=True)
        return payload, u.Tests.toml_mapping(
            u.Tests.toml_mapping(payload["tool"])["ruff"],
        )

    @staticmethod
    def test_typecheck_policy_keeps_tracked_surfaces_visible(
        tool_config_document: m.Infra.ToolConfigDocument,
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
        tm.that(frozenset(tools.pyright.path_rules.env_dirs), eq=tracked_surfaces)
        tm.that(
            hidden_globs.isdisjoint(tools.pyright.path_rules.default_excludes),
            eq=True,
        )
        tm.that(frozenset(tools.pyrefly.path_rules.env_dirs), eq=tracked_surfaces)
        tm.that(hidden_globs.isdisjoint(tools.pyrefly.project_exclude_globs), eq=True)

    def test_ruff_phase_sets_expected_state(
        self,
        tmp_path: Path,
        tool_config_document: m.Infra.ToolConfigDocument,
    ) -> None:
        """Render Ruff policy, drop stale sections, and converge on second apply."""
        ruff_policy = tool_config_document.tools.ruff
        project_dir = tmp_path / "flext-sample"
        (project_dir / "src" / "flext_sample").mkdir(parents=True)
        (project_dir / "src" / "flext_sample" / "__init__.py").write_text(
            "",
            encoding="utf-8",
        )
        stale_pattern = "stale-pattern.py"

        payload, ruff = self._applied(
            tool_config_document,
            project_dir,
            '[lint]\nselect = ["E501"]\n'
            f'[tool.ruff.lint.per-file-ignores]\n"{stale_pattern}" = ["E402"]\n',
        )

        tm.that(payload, lacks="lint")
        # A project without workspace declarations adds no exclusions (the
        # empty list leaves the key absent), and Ruff keeps its own default
        # excludes (never a replacement list).
        tm.that(ruff, lacks="extend-exclude")
        tm.that(ruff, lacks="exclude")
        tm.that(ruff["line-length"], eq=ruff_policy.line_length)
        tm.that(ruff["target-version"], eq=ruff_policy.target_version)
        # The declared src list stays the SSOT; the projection filters it to
        # roots that exist (a retired tree must not name analyzer entries),
        # with roots the active plan is materializing accepted as present.
        tm.that(
            frozenset(u.Tests.toml_strings(ruff["src"])),
            eq=frozenset(
                root for root in ruff_policy.src if (project_dir / root).is_dir()
            ),
        )
        tm.that(
            u.Tests.toml_mapping(ruff["format"])["docstring-code-format"],
            eq=ruff_policy.format.docstring_code_format,
        )
        lint = u.Tests.toml_mapping(ruff["lint"])
        tm.that(
            list(u.Tests.toml_strings(lint["unfixable"])),
            eq=sorted(ruff_policy.lint.unfixable),
        )
        tm.that(
            list(u.Tests.toml_strings(lint["extend-safe-fixes"])),
            eq=sorted(ruff_policy.lint.extend_safe_fixes),
        )
        tm.that(
            list(u.Tests.toml_strings(lint["ignore"])),
            eq=list(ruff_policy.lint.ignore),
        )
        tm.that(
            list(
                u.Tests.toml_strings(
                    u.Tests.toml_mapping(lint["isort"])["known-first-party"],
                ),
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

    @staticmethod
    def test_project_cannot_declare_its_own_ruff_exemption(
        tmp_path: Path,
    ) -> None:
        """Per-file exemptions live only at the tooling owner, never per project."""
        project_dir = tmp_path / "flext-sample"
        config_dir = project_dir / "config"
        config_dir.mkdir(parents=True)
        (config_dir / "sample.yaml").write_text(
            "ManagedArtifacts:\n"
            "  Ruff:\n"
            "    per_file_ignores:\n"
            "      src/flext_sample/_config.py: [N802]\n",
            encoding="utf-8",
        )

        with pytest.raises(m.ValidationError):
            u.Infra.load_project_managed_artifacts(project_dir)

    def test_ruff_phase_skips_nonmember_workspace_namespaces(
        self,
        tmp_path: Path,
        tool_config_document: m.Infra.ToolConfigDocument,
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
            '[project]\nname = "flext-core"\nversion = "0.1.0"\n',
            encoding="utf-8",
        )

        _, ruff = self._applied(
            tool_config_document,
            repository_root,
            'dependencies = ["flext-core>=0.1.0"]\n',
        )

        known_first_party = u.Tests.toml_strings(
            u.Tests.toml_mapping(u.Tests.toml_mapping(ruff["lint"])["isort"])[
                "known-first-party"
            ],
        )
        tm.that(known_first_party, has="flext_core")
        tm.that(known_first_party, lacks="demo_migration_tool")
