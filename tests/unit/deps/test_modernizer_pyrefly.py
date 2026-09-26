"""Pyrefly phase tests for deps modernizer."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import (
    FlextInfraEnsurePyreflyConfigPhase,
    FlextInfraExtraPathsManager,
    FlextInfraPyprojectModernizer,
    c,
    config,
)
from tests import t, u
from tests.unit.deps.extra_paths_support import ExtraPathsTestSupport

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraModernizerPyrefly:
    """Tests pyrefly settings phase behavior."""

    @staticmethod
    def _applied(
        source: str = "",
        *,
        is_root: bool = True,
        project_dir: Path | None = None,
        declared_python_dirs: t.StrSequence | None = None,
    ) -> t.Triple[t.MutableJsonMapping, t.JsonMapping, t.StrSequence]:
        """Apply the Pyrefly phase once; return payload, pyrefly table, and changes."""
        payload = t.Infra.MUTABLE_INFRA_MAPPING_ADAPTER.validate_python(
            u.Tests.toml_payload(source)
        )
        changes = FlextInfraEnsurePyreflyConfigPhase(
            config.Infra.tooling
        ).apply_payload(
            payload,
            is_root=is_root,
            project_dir=project_dir,
            paths_manager=(
                None
                if project_dir is None
                else FlextInfraExtraPathsManager(repository_root=project_dir.parent)
            ),
            declared_python_dirs=declared_python_dirs or (),
            declared_python_dirs_are_complete=declared_python_dirs is not None,
        )
        pyrefly = u.Tests.toml_mapping(u.Tests.toml_mapping(payload["tool"])["pyrefly"])
        return payload, pyrefly, changes

    def test_modernizer_omits_checkout_specific_analyzer_virtualenvs(
        self, tmp_path: Path
    ) -> None:
        """Keep shared analyzer config invariant across checkout topologies."""
        rules = config.Infra.tooling.tools.pyright.path_rules
        (tmp_path / rules.venv_name).mkdir()
        child_origin = tmp_path / "child-origin"
        child_origin.mkdir()
        tm.ok(u.Cli.run_raw(["git", "init"], cwd=child_origin))
        pyproject_text = "[project]\nname = 'fixture-child'\nversion = '0.1.0'\n"
        (child_origin / "pyproject.toml").write_text(pyproject_text, encoding="utf-8")
        tm.ok(u.Cli.run_raw(["git", "add", "pyproject.toml"], cwd=child_origin))
        tm.ok(
            u.Cli.run_raw(
                [
                    "git",
                    "-c",
                    "user.name=FLEXT Tests",
                    "-c",
                    "user.email=tests@flext.dev",
                    "commit",
                    "-m",
                    "fixture",
                ],
                cwd=child_origin,
            )
        )
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        tm.ok(u.Cli.run_raw(["git", "init"], cwd=workspace))
        tm.ok(
            u.Cli.run_raw(
                [
                    "git",
                    "-c",
                    "protocol.file.allow=always",
                    "submodule",
                    "add",
                    str(child_origin),
                    "attached",
                ],
                cwd=workspace,
            )
        )
        linked = tmp_path / "linked"
        tm.ok(
            u.Cli.run_raw(
                ["git", "worktree", "add", "--detach", str(linked)], cwd=child_origin
            )
        )
        for project_dir in (workspace / "attached", linked):
            pyproject = project_dir / "pyproject.toml"
            rendered = tm.ok(
                FlextInfraPyprojectModernizer(
                    repository_root=project_dir, skip_comments=True, skip_check=True
                ).conform_source(pyproject.read_text(encoding="utf-8"), path=pyproject)
            )
            tm.that(
                u.Tests.toml_table_at(rendered, "tool", "pyrefly"),
                lacks="python-interpreter-path",
            )
            pyright = u.Tests.toml_table_at(rendered, "tool", "pyright")
            tm.that(pyright, lacks="venv")
            tm.that(pyright, lacks="venvPath")

    def test_root_payload_receives_canonical_fields(self) -> None:
        """Root payloads receive version, default search path, and strict errors."""
        pyrefly_policy = config.Infra.tooling.tools.pyrefly
        _, pyrefly, changes = self._applied()
        tm.that(changes, empty=False)
        tm.that(pyrefly["python-version"], eq=pyrefly_policy.python_version)
        tm.that(
            list(u.Tests.strings(pyrefly["search-path"])), eq=[c.Infra.DEFAULT_SRC_DIR]
        )
        tm.that(
            set(u.Tests.toml_mapping(pyrefly["errors"])),
            eq=set(pyrefly_policy.strict_errors),
        )

    @pytest.mark.parametrize(
        "retired_key",
        ["fallback-python-interpreter-name", "ignore-errors-in-generated-code"],
    )
    def test_retired_settings_are_removed(self, retired_key: str) -> None:
        """Retired interpreter and suppression settings leave the table."""
        _, pyrefly, changes = self._applied(
            f'[tool.pyrefly]\n{retired_key} = "python"\n'
        )
        tm.that(pyrefly, lacks=retired_key)
        tm.that(changes, has=f"tool.pyrefly.{retired_key} removed")

    def test_stale_error_keys_are_removed(self) -> None:
        """Error keys outside the strict policy are removed, policy keys stay."""
        stale_key = "annotation-mismatch-retired"
        _, pyrefly, changes = self._applied(
            f'[tool.pyrefly.errors]\n{stale_key} = "error"\n'
        )
        errors = u.Tests.toml_mapping(pyrefly["errors"])
        tm.that(errors, lacks=stale_key)
        tm.that(set(errors), eq=set(config.Infra.tooling.tools.pyrefly.strict_errors))
        tm.that(changes, has=f"tool.pyrefly.errors.{stale_key} removed")

    def test_phase_is_idempotent(self) -> None:
        """A second Pyrefly run over the converged payload changes nothing."""
        payload, _, _ = self._applied()
        second = FlextInfraEnsurePyreflyConfigPhase(config.Infra.tooling).apply_payload(
            payload, is_root=True
        )
        tm.that(second, empty=True)

    def test_project_context_contributes_existing_source_directories(
        self, tmp_path: Path
    ) -> None:
        """Project context keeps the source import root first, then the project root."""
        rules = config.Infra.tooling.tools.pyrefly.path_rules
        project_dir = tmp_path / "flext-core"
        for directory in rules.env_dirs:
            (project_dir / directory).mkdir(parents=True)
        (project_dir / "tests" / "test_placeholder.py").write_text(
            "VALUE = 1\n", encoding="utf-8"
        )

        _, pyrefly, _ = self._applied(is_root=False, project_dir=project_dir)

        tm.that(
            list(u.Tests.strings(pyrefly["search-path"])),
            eq=[rules.source_dir, rules.project_root],
        )

    def test_declared_future_roots_are_deterministic(self, tmp_path: Path) -> None:
        """Keep pre-write import roots identical across repeated declarations."""
        rules = config.Infra.tooling.tools.pyrefly.path_rules
        declared = (rules.source_dir, rules.env_dirs[1])
        project_dir = tmp_path / "flext-core"
        project_dir.mkdir()

        _, first, _ = self._applied(
            is_root=False, project_dir=project_dir, declared_python_dirs=declared
        )
        _, second, _ = self._applied(
            is_root=False, project_dir=project_dir, declared_python_dirs=declared
        )

        tm.that(first["search-path"], eq=second["search-path"])
        tm.that(
            list(u.Tests.strings(first[c.Infra.PROJECT_INCLUDES])),
            eq=sorted(f"{directory}/**/*.py*" for directory in declared),
        )

    def test_complete_empty_roots_do_not_rediscover_disk(self, tmp_path: Path) -> None:
        """A complete empty declaration keeps project-includes empty."""
        rules = config.Infra.tooling.tools.pyrefly.path_rules
        project_dir = tmp_path / "flext-core"
        (project_dir / rules.source_dir).mkdir(parents=True)

        _, pyrefly, _ = self._applied(
            is_root=False, project_dir=project_dir, declared_python_dirs=()
        )

        tm.that(list(u.Tests.strings(pyrefly[c.Infra.PROJECT_INCLUDES])), eq=[])

    def test_render_context_includes_live_roots_the_scaffold_never_creates(
        self, tmp_path: Path
    ) -> None:
        """A real env dir reaches project-includes even if no template creates it."""
        rules = config.Infra.tooling.tools.pyrefly.path_rules
        source_dir = rules.source_dir
        undeclared_env_dir = next(
            directory
            for directory in rules.env_dirs
            if directory not in {source_dir, "tests"}
        )
        project_dir = tmp_path / "flext-consumer"
        (project_dir / source_dir).mkdir(parents=True)
        (project_dir / source_dir / "module.py").write_text(
            "VALUE = 1\n", encoding="utf-8"
        )
        (project_dir / undeclared_env_dir).mkdir()
        (project_dir / undeclared_env_dir / "demo.py").write_text(
            "VALUE = 2\n", encoding="utf-8"
        )

        tooling_runtime = tm.ok(
            FlextInfraPyprojectModernizer(
                repository_root=tmp_path, skip_check=True
            ).resolve_tooling_context(
                project_name="flext-consumer",
                package_name="flext_consumer",
                path=project_dir / c.PYPROJECT_FILENAME,
                declared_python_dirs=(source_dir,),
                declared_python_dirs_are_complete=True,
            )
        )

        tm.that(
            tooling_runtime.pyrefly_project_includes,
            has=f"{undeclared_env_dir}/**/*.py*",
        )
        tm.that(tooling_runtime.pyrefly_project_includes, has=f"{source_dir}/**/*.py*")

    def test_pyright_include_feeds_project_includes(self, tmp_path: Path) -> None:
        """Existing Pyright roots feed project-scoped Pyrefly includes."""
        project_dir = tmp_path / "flext-core"
        for directory in ("src", "tests"):
            (project_dir / directory).mkdir(parents=True)
        (project_dir / "src" / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
        (project_dir / c.PYPROJECT_FILENAME).write_text(
            "[tool.pyright]\ninclude = ['src']\n", encoding="utf-8"
        )

        _, pyrefly, _ = self._applied(is_root=False, project_dir=project_dir)

        tm.that(
            list(u.Tests.strings(pyrefly[c.Infra.PROJECT_INCLUDES])),
            eq=["src/**/*.py*"],
        )

    def test_pyright_include_globs_derive_existing_python_roots(
        self, tmp_path: Path
    ) -> None:
        """Derive canonical recursive selectors from existing Python roots."""
        project_dir = tmp_path / "flext-core"
        (project_dir / "src").mkdir(parents=True)
        (project_dir / "tests" / "unit").mkdir(parents=True)
        (project_dir / "scripts").mkdir()
        (project_dir / "src" / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
        (project_dir / "tests" / "unit" / "test_module.py").write_text(
            "", encoding="utf-8"
        )
        (project_dir / "scripts" / "check.py").write_text("", encoding="utf-8")
        (project_dir / c.PYPROJECT_FILENAME).write_text(
            "[tool.pyright]\n"
            "include = ['src', 'tests/unit/**/*.py', 'scripts/check.py']\n",
            encoding="utf-8",
        )

        includes = FlextInfraExtraPathsManager(
            repository_root=tmp_path
        ).pyrefly_project_includes(project_dir=project_dir, is_root=False)

        tm.that(includes, eq=["scripts/**/*.py*", "src/**/*.py*", "tests/**/*.py*"])

    def test_root_context_keeps_workspace_dependencies_out_of_search_path(
        self, tmp_path: Path
    ) -> None:
        """Root context keeps workspace dependencies out of search-path."""
        rules = config.Infra.tooling.tools.pyrefly.path_rules
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "__init__.py").write_text("", encoding="utf-8")
        _ = ExtraPathsTestSupport.workspace_with_dependency(tmp_path)
        payload = t.Infra.MUTABLE_INFRA_MAPPING_ADAPTER.validate_python({})

        _ = FlextInfraEnsurePyreflyConfigPhase(config.Infra.tooling).apply_payload(
            payload,
            is_root=True,
            project_dir=tmp_path,
            paths_manager=FlextInfraExtraPathsManager(repository_root=tmp_path),
        )

        pyrefly = u.Tests.toml_mapping(u.Tests.toml_mapping(payload["tool"])["pyrefly"])
        tm.that(
            list(u.Tests.strings(pyrefly["search-path"])),
            eq=[rules.source_dir, rules.project_root],
        )
