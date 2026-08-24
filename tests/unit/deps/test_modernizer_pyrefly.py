"""Pyrefly phase tests for deps modernizer."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import TYPE_CHECKING

from flext_infra import c, config
from flext_infra.deps.extra_paths import FlextInfraExtraPathsManager
from flext_infra.deps.modernizer import FlextInfraPyprojectModernizer
from flext_infra.deps.phases.ensure_pyrefly import FlextInfraEnsurePyreflyConfigPhase
from flext_tests import tm
from tests import t, u

if TYPE_CHECKING:
    from pathlib import Path

    from tests import m


class TestsFlextInfraModernizerPyrefly:
    """Tests pyrefly settings phase behavior."""

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
        attached = workspace / "attached"
        for project_dir in (attached, linked):
            changes = FlextInfraPyprojectModernizer(
                workspace_root=project_dir,
                apply_changes=True,
                skip_comments=True,
                skip_check=True,
            ).process_file(
                project_dir / "pyproject.toml",
                canonical_dev=(),
                dry_run=False,
                skip_comments=True,
            )
            tm.that(changes, lacks="failed to resolve")

        attached_payload = t.Cli.JSON_MAPPING_ADAPTER.validate_python(
            u.Cli.toml_mapping_from_text(
                (attached / "pyproject.toml").read_text(encoding="utf-8")
            )
        )
        linked_payload = t.Cli.JSON_MAPPING_ADAPTER.validate_python(
            u.Cli.toml_mapping_from_text(
                (linked / "pyproject.toml").read_text(encoding="utf-8")
            )
        )
        attached_tool = u.Cli.json_as_mapping(attached_payload["tool"])
        linked_tool = u.Cli.json_as_mapping(linked_payload["tool"])
        attached_pyrefly = u.Cli.json_as_mapping(attached_tool["pyrefly"])
        linked_pyrefly = u.Cli.json_as_mapping(linked_tool["pyrefly"])
        attached_pyright = u.Cli.json_as_mapping(attached_tool["pyright"])
        linked_pyright = u.Cli.json_as_mapping(linked_tool["pyright"])
        tm.that(attached_pyrefly, lacks="python-interpreter-path")
        tm.that(attached_pyright, lacks="venv")
        tm.that(attached_pyright, lacks="venvPath")
        tm.that(linked_pyrefly, lacks="python-interpreter-path")
        tm.that(linked_pyright, lacks="venv")
        tm.that(linked_pyright, lacks="venvPath")

    def test_ensure_pyrefly_config_sets_fields_root(
        self, tool_config_document: m.Infra.ToolConfigDocument
    ) -> None:
        """Verify root projects receive the canonical Pyrefly fields."""
        doc = u.Cli.toml_document()
        doc["tool"] = u.Cli.toml_table()
        phase = FlextInfraEnsurePyreflyConfigPhase(tool_config_document)
        _ = phase.apply(doc, is_root=True)

    def test_ensure_pyrefly_config_non_root(
        self, tool_config_document: m.Infra.ToolConfigDocument
    ) -> None:
        """Verify child projects receive Pyrefly configuration changes."""
        doc = u.Cli.toml_document()
        doc["tool"] = u.Cli.toml_table()
        changes = FlextInfraEnsurePyreflyConfigPhase(tool_config_document).apply(
            doc, is_root=False
        )
        tm.that(changes, empty=False)

    def test_ensure_pyrefly_config_removes_fallback_interpreter_name(
        self, tool_config_document: m.Infra.ToolConfigDocument
    ) -> None:
        """Verify the obsolete fallback interpreter setting is removed."""
        doc = u.Cli.toml_document()
        doc["tool"] = u.Cli.toml_table()
        tool = doc["tool"]
        tm.that(tool, is_=MutableMapping)
        tool["pyrefly"] = u.Cli.toml_table()
        pyrefly = tool["pyrefly"]
        tm.that(pyrefly, is_=MutableMapping)
        pyrefly["fallback-python-interpreter-name"] = "python"

        changes = FlextInfraEnsurePyreflyConfigPhase(tool_config_document).apply(
            doc, is_root=True
        )

        tm.that(pyrefly, lacks="python-interpreter-path")
        tm.that("fallback-python-interpreter-name" in pyrefly, eq=False)
        tm.that(
            any(
                "tool.pyrefly.fallback-python-interpreter-name removed" in change
                for change in changes
            ),
            eq=True,
        )

    def test_ensure_pyrefly_config_phase_apply_python_version(
        self, tool_config_document: m.Infra.ToolConfigDocument
    ) -> None:
        """Verify the canonical Python version is written."""
        doc = u.Cli.toml_document()
        doc["tool"] = u.Cli.toml_table()
        tool = doc["tool"]
        tm.that(tool, is_=MutableMapping)
        tool["pyrefly"] = u.Cli.toml_table()
        _ = FlextInfraEnsurePyreflyConfigPhase(tool_config_document).apply(
            doc, is_root=True
        )
        pyrefly = tool["pyrefly"]
        tm.that(pyrefly, is_=MutableMapping)
        tm.that(u.Cli.toml_unwrap_item(pyrefly["python-version"]), eq="3.13")

    def test_ensure_pyrefly_config_phase_apply_ignore_errors(
        self, tool_config_document: m.Infra.ToolConfigDocument
    ) -> None:
        """Verify generated-code error handling follows canonical policy."""
        doc = u.Cli.toml_document()
        doc["tool"] = u.Cli.toml_table()
        tool = doc["tool"]
        tm.that(tool, is_=MutableMapping)
        tool["pyrefly"] = u.Cli.toml_table()
        _ = FlextInfraEnsurePyreflyConfigPhase(tool_config_document).apply(
            doc, is_root=True
        )
        pyrefly = tool["pyrefly"]
        tm.that(pyrefly, is_=MutableMapping)
        tm.that(
            u.Cli.toml_unwrap_item(pyrefly["ignore-errors-in-generated-code"]), eq=True
        )

    def test_ensure_pyrefly_config_phase_apply_search_path(
        self, tool_config_document: m.Infra.ToolConfigDocument
    ) -> None:
        """Verify the default Pyrefly search path is written."""
        doc = u.Cli.toml_document()
        doc["tool"] = u.Cli.toml_table()
        tool = doc["tool"]
        tm.that(tool, is_=MutableMapping)
        tool["pyrefly"] = u.Cli.toml_table()
        _ = FlextInfraEnsurePyreflyConfigPhase(tool_config_document).apply(
            doc, is_root=True
        )
        pyrefly = tool["pyrefly"]
        tm.that(pyrefly, is_=MutableMapping)
        tm.that(u.Cli.toml_unwrap_item(pyrefly["search-path"]), eq=["src"])

    def test_ensure_pyrefly_config_phase_apply_search_path_with_project_context(
        self, tmp_path: Path, tool_config_document: m.Infra.ToolConfigDocument
    ) -> None:
        """Verify project context contributes existing source directories."""
        project_dir = tmp_path / "flext-core"
        project_dir.mkdir()
        for directory in ("src", "tests", "examples", "scripts"):
            (project_dir / directory).mkdir()
        (project_dir / "tests" / "test_placeholder.py").write_text(
            "from flext_tests import tm\n\n"
            "def test_placeholder() -> None:\n"
            "    tm.that(True, eq=True)\n",
            encoding="utf-8",
        )

        doc = u.Cli.toml_document()
        doc["tool"] = u.Cli.toml_table()
        tool = doc["tool"]
        tm.that(tool, is_=MutableMapping)
        tool["pyrefly"] = u.Cli.toml_table()

        _ = FlextInfraEnsurePyreflyConfigPhase(tool_config_document).apply(
            doc,
            is_root=False,
            project_dir=project_dir,
            paths_manager=FlextInfraExtraPathsManager(workspace_root=tmp_path),
        )

        pyrefly = tool["pyrefly"]
        tm.that(pyrefly, is_=MutableMapping)
        search_path = u.Cli.toml_unwrap_item(pyrefly["search-path"])
        tm.that(search_path, eq=["src", "."])

    def test_ensure_pyrefly_config_uses_declared_future_source_root(
        self, tmp_path: Path, tool_config_document: m.Infra.ToolConfigDocument
    ) -> None:
        """Keep pre-write import roots identical to post-write discovery."""
        rules = tool_config_document.tools.pyrefly.path_rules
        declared_python_dirs = (rules.source_dir, rules.env_dirs[1])
        project_dir = tmp_path / "flext-core"
        project_dir.mkdir()
        doc = u.Cli.toml_document()

        _ = FlextInfraEnsurePyreflyConfigPhase(tool_config_document).apply(
            doc,
            is_root=False,
            project_dir=project_dir,
            paths_manager=FlextInfraExtraPathsManager(workspace_root=tmp_path),
            declared_python_dirs=declared_python_dirs,
            declared_python_dirs_are_complete=True,
        )

        tool = doc["tool"]
        tm.that(tool, is_=MutableMapping)
        pyrefly = tool["pyrefly"]
        tm.that(pyrefly, is_=MutableMapping)
        tm.that(
            u.Cli.toml_unwrap_item(pyrefly["search-path"]),
            eq=[rules.source_dir, *rules.project_shared_search_paths],
        )
        tm.that(
            u.Cli.toml_unwrap_item(pyrefly[c.Infra.PROJECT_INCLUDES]),
            eq=[f"{directory}/**/*.py*" for directory in declared_python_dirs],
        )

    def test_ensure_pyrefly_config_complete_empty_roots_do_not_rediscover_disk(
        self, tmp_path: Path, tool_config_document: m.Infra.ToolConfigDocument
    ) -> None:
        rules = tool_config_document.tools.pyrefly.path_rules
        project_dir = tmp_path / "flext-core"
        (project_dir / rules.source_dir).mkdir(parents=True)
        doc = u.Cli.toml_document()

        _ = FlextInfraEnsurePyreflyConfigPhase(tool_config_document).apply(
            doc,
            is_root=False,
            project_dir=project_dir,
            paths_manager=FlextInfraExtraPathsManager(workspace_root=tmp_path),
            declared_python_dirs=(),
            declared_python_dirs_are_complete=True,
        )

        tool = doc["tool"]
        tm.that(tool, is_=MutableMapping)
        pyrefly = tool["pyrefly"]
        tm.that(pyrefly, is_=MutableMapping)
        tm.that(
            u.Cli.toml_unwrap_item(pyrefly["search-path"]),
            eq=list(rules.project_shared_search_paths),
        )
        tm.that(u.Cli.toml_unwrap_item(pyrefly[c.Infra.PROJECT_INCLUDES]), eq=[])

    def test_ensure_pyrefly_config_uses_pyright_include_when_available(
        self, tmp_path: Path, tool_config_document: m.Infra.ToolConfigDocument
    ) -> None:
        """Verify Pyright include paths feed project-scoped Pyrefly config."""
        project_dir = tmp_path / "flext-core"
        project_dir.mkdir()
        for directory in ("src", "tests"):
            (project_dir / directory).mkdir()
        (project_dir / c.Infra.PYPROJECT_FILENAME).write_text(
            "[tool.pyright]\ninclude = ['src']\n", encoding="utf-8"
        )

        doc = u.Cli.toml_document()
        doc["tool"] = u.Cli.toml_table()
        tool = doc["tool"]
        tm.that(tool, is_=MutableMapping)
        tool["pyrefly"] = u.Cli.toml_table()

        _ = FlextInfraEnsurePyreflyConfigPhase(tool_config_document).apply(
            doc,
            is_root=False,
            project_dir=project_dir,
            paths_manager=FlextInfraExtraPathsManager(workspace_root=tmp_path),
        )

        pyrefly = tool["pyrefly"]
        tm.that(pyrefly, is_=MutableMapping)
        project_includes = u.Cli.toml_unwrap_item(pyrefly[c.Infra.PROJECT_INCLUDES])
        tm.that(project_includes, eq=["src/**/*.py*"])

    def test_pyright_include_globs_preserve_declared_files_and_patterns(
        self, tmp_path: Path
    ) -> None:
        """Keep explicit file/glob selectors while expanding directory roots."""
        project_dir = tmp_path / "flext-core"
        project_dir.mkdir()
        (project_dir / c.Infra.PYPROJECT_FILENAME).write_text(
            "[tool.pyright]\n"
            "include = ['src', 'tests/unit/**/*.py', 'scripts/check.py']\n",
            encoding="utf-8",
        )

        includes = FlextInfraExtraPathsManager(
            workspace_root=tmp_path
        ).pyrefly_project_includes(project_dir=project_dir, is_root=False)

        tm.that(includes, eq=["scripts/check.py", "src/**/*.py*", "tests/unit/**/*.py"])

    def test_ensure_pyrefly_config_phase_apply_search_path_with_root_context(
        self, tmp_path: Path, tool_config_document: m.Infra.ToolConfigDocument
    ) -> None:
        """Verify root context keeps workspace dependencies out of search-path."""
        for directory in ("src", "tests"):
            (tmp_path / directory).mkdir()
        (tmp_path / "tests" / "__init__.py").write_text("", encoding="utf-8")
        (tmp_path / "pyproject.toml").write_text(
            (
                "[project]\n"
                "name = 'flext'\n"
                "dependencies = ['flext-core']\n"
                "[tool.uv.workspace]\n"
                "members = ['flext-core']\n"
            ),
            encoding="utf-8",
        )
        dep_root = tmp_path / "flext-core"
        dep_root.mkdir()
        (dep_root / ".git").mkdir()
        (dep_root / "Makefile").write_text("", encoding="utf-8")
        (dep_root / "pyproject.toml").write_text(
            "[project]\nname = 'flext-core'\n", encoding="utf-8"
        )
        (dep_root / "src" / "flext_core").mkdir(parents=True)
        (dep_root / "src" / "flext_core" / "__init__.py").write_text(
            "", encoding="utf-8"
        )

        doc = u.Cli.toml_document()
        doc["tool"] = u.Cli.toml_table()
        tool = doc["tool"]
        tm.that(tool, is_=MutableMapping)
        tool["pyrefly"] = u.Cli.toml_table()

        _ = FlextInfraEnsurePyreflyConfigPhase(tool_config_document).apply(
            doc,
            is_root=True,
            project_dir=tmp_path,
            paths_manager=FlextInfraExtraPathsManager(workspace_root=tmp_path),
        )

        pyrefly = tool["pyrefly"]
        tm.that(pyrefly, is_=MutableMapping)
        search_path = u.Cli.toml_unwrap_item(pyrefly["search-path"])
        tm.that(search_path, eq=["src", "."])

    def test_ensure_pyrefly_config_phase_apply_errors(
        self, tool_config_document: m.Infra.ToolConfigDocument
    ) -> None:
        """Verify the canonical Pyrefly error table is populated."""
        doc = u.Cli.toml_document()
        doc["tool"] = u.Cli.toml_table()
        tool = doc["tool"]
        tm.that(tool, is_=MutableMapping)
        tool["pyrefly"] = u.Cli.toml_table()
        _ = FlextInfraEnsurePyreflyConfigPhase(tool_config_document).apply(
            doc, is_root=True
        )
        pyrefly = tool["pyrefly"]
        tm.that(pyrefly, is_=MutableMapping)
        errors = pyrefly["errors"]
        tm.that(errors, is_=MutableMapping)
        tm.that(len(errors), gt=0)

    def test_ensure_pyrefly_config_phase_removes_stale_error_keys(
        self, tool_config_document: m.Infra.ToolConfigDocument
    ) -> None:
        """Verify stale error keys are removed from TOML documents."""
        doc = u.Cli.toml_document()
        doc["tool"] = u.Cli.toml_table()
        tool = doc["tool"]
        tm.that(tool, is_=MutableMapping)
        tool["pyrefly"] = u.Cli.toml_table()
        pyrefly = tool["pyrefly"]
        tm.that(pyrefly, is_=MutableMapping)
        pyrefly["errors"] = u.Cli.toml_table()
        errors = pyrefly["errors"]
        tm.that(errors, is_=MutableMapping)
        errors["annotation-mismatch"] = "error"

        changes = FlextInfraEnsurePyreflyConfigPhase(tool_config_document).apply(
            doc, is_root=True
        )

        tm.that("annotation-mismatch" in errors, eq=False)
        tm.that("bad-argument-count" in errors, eq=True)
        tm.that(
            any(
                "tool.pyrefly.errors.annotation-mismatch removed" in c for c in changes
            ),
            eq=True,
        )

    def test_ensure_pyrefly_config_payload_removes_stale_error_keys(
        self, tool_config_document: m.Infra.ToolConfigDocument
    ) -> None:
        """Verify stale error keys are removed from plain payloads."""
        errors: t.JsonDict = {"annotation-mismatch": "error"}
        pyrefly: t.JsonDict = {"errors": errors}
        tool: t.JsonDict = {"pyrefly": pyrefly}
        payload: t.MutableJsonMapping = {"tool": tool}

        changes = FlextInfraEnsurePyreflyConfigPhase(
            tool_config_document
        ).apply_payload(payload, is_root=True)

        errors_after = t.Infra.MUTABLE_INFRA_MAPPING_ADAPTER.validate_python(
            u.Cli.toml_mapping_path(payload, (c.Infra.TOOL, c.Infra.PYREFLY, "errors"))
        )
        tm.that("annotation-mismatch" in errors_after, eq=False)
        tm.that("bad-argument-count" in errors_after, eq=True)
        tm.that(
            any(
                "tool.pyrefly.errors.annotation-mismatch removed" in c for c in changes
            ),
            eq=True,
        )

    def test_ensure_pyrefly_config_phase_is_idempotent(
        self, tool_config_document: m.Infra.ToolConfigDocument
    ) -> None:
        """Verify a second Pyrefly phase run produces no changes."""
        doc = u.Cli.toml_document()
        phase = FlextInfraEnsurePyreflyConfigPhase(tool_config_document)

        _ = phase.apply(doc, is_root=True)
        second_changes = phase.apply(doc, is_root=True)

        tm.that(second_changes, empty=True)
