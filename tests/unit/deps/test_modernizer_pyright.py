"""Pyright phase tests for deps modernizer."""

from __future__ import annotations

from collections.abc import MutableMapping, Sequence
from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import (
    FlextInfraEnsurePyrightConfigPhase,
    FlextInfraPyprojectModernizer,
    u as infra_u,
)
from tests import t, u

if TYPE_CHECKING:
    from pathlib import Path

    from tests import m


class TestsFlextInfraDepsModernizerPyright:
    """Declarative tests for generated Pyright configuration."""

    @staticmethod
    def _applied(
        tool_config_document: m.Infra.ToolConfigDocument,
        *,
        is_root: bool,
        repository_root: Path | None = None,
        project_dir: Path | None = None,
        declared_python_dirs: t.StrSequence = (),
        declared_python_dirs_are_complete: bool = False,
    ) -> t.JsonMapping:
        """Apply the phase twice to an empty payload; return the converged table."""
        payload = t.Infra.MUTABLE_INFRA_MAPPING_ADAPTER.validate_python({})
        phase = FlextInfraEnsurePyrightConfigPhase(tool_config_document)
        changes = [
            phase.apply_payload(
                payload,
                is_root=is_root,
                repository_root=repository_root,
                project_dir=project_dir,
                declared_python_dirs=declared_python_dirs,
                declared_python_dirs_are_complete=declared_python_dirs_are_complete,
            )
            for _ in range(2)
        ]
        tm.that(changes[0], empty=False)
        tm.that(changes[1], empty=True)
        pyright = u.Tests.toml_mapping(u.Tests.toml_mapping(payload["tool"])["pyright"])
        # Shared config leaves environment selection to Make.
        tm.that(pyright, lacks="venv")
        tm.that(pyright, lacks="venvPath")
        return pyright

    @staticmethod
    def _sample_project(tmp_path: Path, source_dir_name: str) -> Path:
        """Create one governed flext-sample project with a src package and manifest."""
        project_dir = tmp_path / "flext-sample"
        source_dir = project_dir / source_dir_name / "flext_sample"
        source_dir.mkdir(parents=True)
        (source_dir / "__init__.py").write_text("", encoding="utf-8")
        (project_dir / "pyproject.toml").write_text(
            "[project]\nname='flext-sample'\nversion='0.1.0'\n", encoding="utf-8"
        )
        u.Tests.write_project_beads_config(project_dir, "flext-sample")
        return project_dir

    @staticmethod
    def _workspace(tmp_path: Path, *members: str) -> None:
        """Declare one governed workspace root with governed member manifests."""
        (tmp_path / "pyproject.toml").write_text(
            "[project]\nname='workspace'\nversion='0.1.0'\n", encoding="utf-8"
        )
        for member in members:
            package = tmp_path / member / "src" / member.replace("-", "_")
            package.mkdir(parents=True, exist_ok=True)
            (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
            (tmp_path / member / "pyproject.toml").write_text(
                f"[project]\nname='{member}'\nversion='0.1.0'\n", encoding="utf-8"
            )
            u.Tests.write_project_beads_config(tmp_path / member, member)
        u.Tests.declare_workspace_projects(tmp_path, members)
        u.Tests.write_project_beads_config(tmp_path, "workspace")

    def test_python_discovery_ignores_member_only_container(
        self, tmp_path: Path
    ) -> None:
        """A directory containing only nested projects is not a root source tree."""
        root_source = tmp_path / "src"
        root_source.mkdir()
        (root_source / "root.py").write_text("VALUE = 1\n", encoding="utf-8")
        (tmp_path / "pyproject.toml").write_text(
            "[project]\nname='workspace'\nversion='0.1.0'\n", encoding="utf-8"
        )
        u.Tests.write_project_beads_config(tmp_path, "workspace")
        member = tmp_path / "apps" / "member"
        member_source = member / "src" / "member"
        member_source.mkdir(parents=True)
        (member / "pyproject.toml").write_text(
            "[project]\nname='member'\nversion='0.1.0'\n", encoding="utf-8"
        )
        (member_source / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")

        tm.that(infra_u.Infra.discover_python_dirs(tmp_path), eq=["src"])

    def test_python_discovery_uses_caller_resolved_exclusions(
        self, tmp_path: Path
    ) -> None:
        """Honor the command-scoped topology projection without rediscovery."""
        included = tmp_path / "included"
        excluded = tmp_path / "excluded"
        for directory in (included, excluded):
            directory.mkdir()
            (directory / "module.py").write_text("VALUE = 1\n", encoding="utf-8")

        discovered = infra_u.Infra.discover_python_dirs(
            tmp_path, workspace_excluded_top_dirs=frozenset({excluded.name})
        )

        tm.that(discovered, eq=[included.name])

    def test_root_config_sets_expected_execution_environments(
        self, tmp_path: Path, tool_config_document: m.Infra.ToolConfigDocument
    ) -> None:
        """Render only roots owned by the workspace repository itself."""
        pyright_rules = tool_config_document.tools.pyright
        rules = pyright_rules.path_rules
        self._workspace(tmp_path, "flext-core", "flext-api")
        root_source = tmp_path / rules.source_dir / "workspace"
        root_source.mkdir(parents=True)
        (root_source / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
        (tmp_path / "flext-core" / "tests").mkdir()
        (tmp_path / "flext-core" / "tests" / "test_smoke.py").write_text(
            "VALUE = 1\n", encoding="utf-8"
        )
        detached = tmp_path / "demo-migration-tool"
        (detached / "src").mkdir(parents=True)
        (detached / "pyproject.toml").write_text(
            "[project]\nname='demo-migration-tool'\n", encoding="utf-8"
        )

        pyright = self._applied(
            tool_config_document, is_root=True, repository_root=tmp_path
        )

        tm.that(
            sorted(u.Tests.toml_strings(pyright["exclude"])),
            eq=sorted(set(rules.default_excludes)),
        )
        if rules.ignored_diagnostic_globs:
            tm.that(
                sorted(u.Tests.toml_strings(pyright["ignore"])),
                eq=sorted({*rules.ignored_diagnostic_globs}),
            )
        else:
            tm.that(pyright, lacks="ignore")
        tm.that(list(u.Tests.toml_strings(pyright["include"])), eq=[rules.source_dir])
        tm.that(
            pyright["executionEnvironments"],
            eq=[
                {
                    **pyright_rules.lazy_import_suppressions,
                    **pyright_rules.source_env_suppressions,
                    "root": rules.source_dir,
                    "reportPrivateUsage": rules.source_report_private_usage,
                    "extraPaths": [rules.source_dir, "flext-core/src", "flext-api/src"],
                }
            ],
        )

    def test_root_config_includes_member_src_paths(
        self, tmp_path: Path, tool_config_document: m.Infra.ToolConfigDocument
    ) -> None:
        """Workspace root execution environments include every declared first-party member src path for Pylance resolution."""
        pyright_rules = tool_config_document.tools.pyright
        rules = pyright_rules.path_rules
        _ = (tmp_path / "pyproject.toml").write_text(
            "[project]\nname='workspace'\nversion='0.1.0'\n", encoding="utf-8"
        )
        flext_core = tmp_path / "flext-core"
        flext_api = tmp_path / "flext-api"
        (flext_core / "src").mkdir(parents=True, exist_ok=True)
        (flext_api / "src").mkdir(parents=True, exist_ok=True)
        (flext_core / "src" / "flext_core").mkdir(parents=True, exist_ok=True)
        (flext_core / "src" / "flext_core" / "__init__.py").write_text(
            "VALUE = 1\n", encoding="utf-8"
        )
        (flext_api / "src" / "flext_api").mkdir(parents=True, exist_ok=True)
        (flext_api / "src" / "flext_api" / "__init__.py").write_text(
            "VALUE = 1\n", encoding="utf-8"
        )
        (tmp_path / "src").mkdir(parents=True, exist_ok=True)
        (tmp_path / "src" / "workspace").mkdir(parents=True, exist_ok=True)
        (tmp_path / "src" / "workspace" / "__init__.py").write_text(
            "VALUE = 1\n", encoding="utf-8"
        )
        u.Tests.declare_workspace_projects(tmp_path, ("flext-core", "flext-api"))
        u.Tests.write_project_beads_config(tmp_path, "workspace")
        pyright = self._applied(
            tool_config_document, is_root=True, repository_root=tmp_path
        )
        envs = pyright["executionEnvironments"]
        tm.that(envs, is_=Sequence)
        if not isinstance(envs, Sequence):
            return
        src_env = None
        for entry in envs:
            environment = u.Cli.toml_unwrap_item(entry)
            if isinstance(environment, MutableMapping) and (
                environment.get("root") == rules.source_dir
            ):
                src_env = environment
                break
        tm.that(src_env is not None, eq=True)
        if src_env is None:
            return
        extra_paths = u.Tests.toml_strings(
            u.Cli.toml_unwrap_item(src_env.get("extraPaths", ()))
        )
        tm.that("flext-core/src" in extra_paths, eq=True)
        tm.that("flext-api/src" in extra_paths, eq=True)

    def test_declared_repository_config_sets_expected_execution_environments(
        self, tool_config_document: m.Infra.ToolConfigDocument
    ) -> None:
        """Render every configured standalone analyzer environment."""
        pyright_rules = tool_config_document.tools.pyright
        rules = pyright_rules.path_rules

        pyright = self._applied(tool_config_document, is_root=False)

        tm.that(
            sorted(u.Tests.toml_strings(pyright["include"])), eq=sorted(rules.env_dirs)
        )
        tm.that(
            pyright["executionEnvironments"],
            eq=[
                {
                    **pyright_rules.lazy_import_suppressions,
                    **(
                        pyright_rules.source_env_suppressions
                        if env_dir == rules.source_dir
                        else (
                            pyright_rules.test_like_env_suppressions
                            if env_dir in rules.test_like_dirs
                            else {}
                        )
                    ),
                    "root": env_dir,
                    "reportPrivateUsage": (
                        rules.source_report_private_usage
                        if env_dir == rules.source_dir
                        else rules.test_like_report_private_usage
                    ),
                    "extraPaths": (
                        [rules.source_dir]
                        if env_dir == rules.source_dir
                        else [rules.project_root, rules.source_dir]
                    ),
                }
                for env_dir in rules.env_dirs
            ],
        )

    def test_project_config_uses_canonical_typings_and_fixture_excludes(
        self, tmp_path: Path, tool_config_document: m.Infra.ToolConfigDocument
    ) -> None:
        """Render typed paths and config-owned fixture exclusions."""
        rules = tool_config_document.tools.pyright.path_rules
        project_dir = u.Tests.mk_project(
            tmp_path,
            "flext-sample",
            pyproject="[project]\nname='flext-sample'\nversion='0.1.0'\n",
            with_src=True,
        )
        (project_dir / "src" / "sample.py").write_text("VALUE = 1\n", encoding="utf-8")
        (project_dir / "tests" / "fixtures").mkdir(parents=True)
        (project_dir / "tests" / "test_smoke.py").write_text(
            "VALUE = 1\n", encoding="utf-8"
        )

        pyright = self._applied(
            tool_config_document, is_root=False, project_dir=project_dir
        )

        if rules.ignored_diagnostic_globs:
            tm.that(
                sorted(u.Tests.toml_strings(pyright["ignore"])),
                eq=sorted({*rules.ignored_diagnostic_globs}),
            )
        else:
            tm.that(pyright, lacks="ignore")
        tm.that(
            sorted(u.Tests.toml_strings(pyright["include"])),
            eq=sorted([rules.source_dir, rules.test_like_dirs[0]]),
        )
        tm.that(
            set(u.Tests.toml_strings(pyright["exclude"])).issuperset(
                rules.default_excludes
            ),
            eq=True,
        )

    def test_existing_standalone_uses_complete_declared_roots(
        self, tmp_path: Path, tool_config_document: m.Infra.ToolConfigDocument
    ) -> None:
        """A complete declaration fixes the include set through the modernizer."""
        rules = tool_config_document.tools.pyright.path_rules
        project_dir = self._sample_project(tmp_path, rules.source_dir)
        pyproject = project_dir / "pyproject.toml"

        rendered = tm.ok(
            FlextInfraPyprojectModernizer(
                repository_root=project_dir, skip_check=True, skip_comments=True
            ).conform_source(
                pyproject.read_text(encoding="utf-8"),
                path=pyproject,
                declared_python_dirs=(rules.source_dir, rules.test_like_dirs[0]),
                declared_python_dirs_are_complete=True,
            )
        )

        tm.that(
            list(u.Tests.toml_strings_at(rendered, "tool", "pyright", "include")),
            eq=[rules.source_dir, rules.test_like_dirs[0]],
        )

    def test_existing_standalone_complete_empty_roots_do_not_rediscover_disk(
        self, tmp_path: Path, tool_config_document: m.Infra.ToolConfigDocument
    ) -> None:
        """A complete empty declaration renders no include and no environment."""
        rules = tool_config_document.tools.pyright.path_rules
        project_dir = self._sample_project(tmp_path, rules.source_dir)

        pyright = self._applied(
            tool_config_document,
            is_root=False,
            project_dir=project_dir,
            declared_python_dirs_are_complete=True,
        )

        tm.that(pyright, lacks="include")
        tm.that(pyright["executionEnvironments"], eq=[])

    def test_repository_root_never_adopts_member_analyzer_roots(
        self, tmp_path: Path, tool_config_document: m.Infra.ToolConfigDocument
    ) -> None:
        """Keep member projects under their own manifests and native gates."""
        rules = tool_config_document.tools.pyright.path_rules
        self._workspace(tmp_path, "flext-core")

        fleet = self._applied(
            tool_config_document, is_root=True, repository_root=tmp_path
        )
        declared = self._applied(
            tool_config_document,
            is_root=True,
            repository_root=tmp_path,
            declared_python_dirs=(rules.source_dir,),
        )

        tm.that(declared, eq=fleet)
        tm.that(declared, lacks="include")
        tm.that(declared["executionEnvironments"], eq=[])

    def test_expected_envs_cover_every_analyzer_python_root(
        self, tmp_path: Path, tool_config_document: m.Infra.ToolConfigDocument
    ) -> None:
        """The phase emits an environment for every root the analyzer owner selects.

        ``analyzer_python_roots`` is the single owner of "which directories are
        productive Python roots". A Python file under a directory outside
        ``env_dirs`` (docs/ here) separates that owner from the env list.
        """
        rules = tool_config_document.tools.pyright.path_rules
        source = tmp_path / rules.source_dir
        source.mkdir(parents=True)
        (source / "mod.py").write_text("x = 1\n", encoding="utf-8")
        outside = tmp_path / "docs" / "tools"
        outside.mkdir(parents=True)
        (outside / "validate_docs.py").write_text("y = 2\n", encoding="utf-8")
        (tmp_path / "pyproject.toml").write_text(
            "[project]\nname='workspace'\nversion='0.1.0'\n", encoding="utf-8"
        )
        u.Tests.write_project_beads_config(tmp_path, "workspace")
        discovered = frozenset(infra_u.Infra.discover_python_dirs(tmp_path))
        declared = tuple(d for d in rules.env_dirs if d in discovered)

        pyright = self._applied(
            tool_config_document, is_root=False, project_dir=tmp_path
        )

        tm.that(
            sorted(
                str(u.Tests.toml_mapping(environment)["root"])
                for environment in u.Tests.toml_list(pyright["executionEnvironments"])
            ),
            eq=sorted(infra_u.Infra.analyzer_python_roots(tmp_path, declared)),
        )
