"""Edge-case tests for public modernizer flows."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import FlextInfraPyprojectModernizer
from tests import c, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraDepsModernizerMainExtra:
    """Validate edge cases through the public modernizer API."""

    @staticmethod
    def _ran_modernizer(modernizer_workspace: Path) -> str:
        """Run the constraint-rewriting modernizer and return the rendered root."""
        modernizer = FlextInfraPyprojectModernizer(
            repository_root=modernizer_workspace,
            apply_changes=True,
            rewrite_constraints=True,
            skip_comments=True,
            skip_check=True,
        )

        tm.that(modernizer.run(), eq=0)
        return (modernizer_workspace / c.PYPROJECT_FILENAME).read_text(encoding="utf-8")

    @pytest.mark.parametrize(
        ("content", "expected"),
        [
            pytest.param(None, 2, id="missing-root-pyproject"),
            pytest.param("", 2, id="empty-root-pyproject"),
            pytest.param("[invalid toml {", 2, id="invalid-root-pyproject"),
        ],
    )
    def test_run_handles_root_edge_cases(
        self, tmp_path: Path, content: str | None, expected: int
    ) -> None:
        """Fail loud for missing, empty, or invalid root project contracts."""
        workspace = tmp_path / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        if content is not None:
            (workspace / c.PYPROJECT_FILENAME).write_text(content, encoding="utf-8")
        modernizer = FlextInfraPyprojectModernizer(repository_root=workspace)
        tm.that(modernizer.run(), eq=expected)

    def test_audit_returns_zero_after_workspace_is_canonical(
        self, modernizer_workspace: Path
    ) -> None:
        """Reach a fixed point after one canonical apply."""
        apply_exit = FlextInfraPyprojectModernizer(
            repository_root=modernizer_workspace,
            apply_changes=True,
            skip_comments=True,
            skip_check=True,
        ).run()
        audit_exit = FlextInfraPyprojectModernizer(
            repository_root=modernizer_workspace, audit=True, skip_comments=True
        ).run()
        tm.that(apply_exit, eq=0)
        tm.that(audit_exit, eq=0)

    def test_run_fails_when_selected_project_has_invalid_toml(
        self,
        modernizer_workspace_with_projects: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Reject invalid TOML in a declared member before any write."""
        selected_pyproject = (
            modernizer_workspace_with_projects / "selected" / c.PYPROJECT_FILENAME
        )
        selected_pyproject.write_text("[invalid", encoding="utf-8")
        root_pyproject = modernizer_workspace_with_projects / c.PYPROJECT_FILENAME
        root_before = root_pyproject.read_bytes()
        modernizer = FlextInfraPyprojectModernizer(
            repository_root=modernizer_workspace_with_projects,
            apply_changes=True,
            skip_comments=True,
            skip_check=False,
        )

        tm.that(modernizer.run(), eq=2)
        tm.that(capsys.readouterr().out, has=str(selected_pyproject))
        tm.that(root_pyproject.read_bytes(), eq=root_before)
        tm.that(selected_pyproject.read_text(encoding="utf-8"), eq="[invalid")

    def test_run_rewrite_constraints_uses_provisioned_runtime(
        self, modernizer_workspace: Path
    ) -> None:
        """Rewriting does not require a persisted dependency resolution."""
        modernizer = FlextInfraPyprojectModernizer(
            repository_root=modernizer_workspace,
            apply_changes=True,
            rewrite_constraints=True,
            skip_comments=True,
            skip_check=True,
        )
        tm.that(modernizer.run(), eq=0)
        tm.that((modernizer_workspace / "uv.lock").exists(), eq=False)

    def test_run_rewrite_constraints_keeps_attached_submodule_manifest(
        self, modernizer_workspace: Path
    ) -> None:
        """Read runtime versions without creating a dependency lock in a member."""
        source_repository = modernizer_workspace.parent / "flext-core-source"
        source_repository.mkdir()
        (source_repository / c.PYPROJECT_FILENAME).write_text(
            '[project]\nname = "flext-core"\nversion = "0.12.0-dev"\n', encoding="utf-8"
        )
        package_init = source_repository / "src" / "flext_core" / "__init__.py"
        package_init.parent.mkdir(parents=True)
        package_init.write_text('"""FLEXT Core test package."""\n', encoding="utf-8")
        u.Tests.initialize_git_repo(source_repository)

        (modernizer_workspace / c.PYPROJECT_FILENAME).write_text(
            (
                '[project]\nname = "workspace"\nversion = "0.1.0"\n'
                'dependencies = ["requests>=2.0"]\n\n'
                "[tool.uv.workspace]\n"
                'members = ["flext-core"]\n'
            ),
            encoding="utf-8",
        )
        u.Tests.initialize_git_repo(modernizer_workspace)
        u.Tests.git_bootstrap(
            modernizer_workspace,
            (
                "-c",
                "protocol.file.allow=always",
                "submodule",
                "add",
                str(source_repository),
                "flext-core",
            ),
        )

        exit_code = FlextInfraPyprojectModernizer(
            repository_root=modernizer_workspace,
            apply_changes=True,
            rewrite_constraints=True,
            skip_comments=True,
            skip_check=True,
        ).run()

        tm.that(exit_code, eq=0)
        tm.that((modernizer_workspace / "flext-core" / "uv.lock").exists(), eq=False)
        tm.that(
            (modernizer_workspace / c.PYPROJECT_FILENAME).read_text(encoding="utf-8"),
            has='"requests>=2.0"',
        )

    def test_run_apply_rewrites_dependency_constraints_from_runtime(
        self, modernizer_workspace: Path
    ) -> None:
        """Rewrite registry constraints while preserving internal dependencies."""
        (modernizer_workspace / c.PYPROJECT_FILENAME).write_text(
            (
                "[project]\n"
                'name = "workspace"\n'
                'version = "0.1.0"\n'
                'dependencies = ["requests>=2.0", "httpx[socks]>=0.1; python_version < \'3.14\'", "flext-core"]\n\n'
                "[tool.uv.workspace]\n"
                'members = ["flext-core"]\n\n'
                "[tool.poetry.dependencies]\n"
                'python = ">=3.13,<3.14"\n'
                'rich = ">=10"\n'
                'pendulum = { version = ">=2.0", extras = ["test"] }\n'
                'flext-core = { path = "../flext-core", develop = true }\n'
            ),
            encoding="utf-8",
        )
        member = modernizer_workspace / "flext-core"
        package = member / "src" / "flext_core"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
        (member / c.PYPROJECT_FILENAME).write_text(
            '[project]\nname = "flext-core"\nversion = "0.12.0-dev"\n', encoding="utf-8"
        )

        rendered = TestsFlextInfraDepsModernizerMainExtra._ran_modernizer(
            modernizer_workspace
        )
        tm.that(rendered, has='"requests>=2.0"')
        tm.that(rendered, lacks='"requests>=2.32.4"')

    def test_run_apply_rewrites_constraints_as_open_floor(
        self, modernizer_workspace: Path
    ) -> None:
        """Use installed versions as floors without imposing an artificial upper bound."""
        (modernizer_workspace / c.PYPROJECT_FILENAME).write_text(
            (
                "[project]\n"
                'name = "workspace"\n'
                'version = "0.1.0"\n'
                'dependencies = ["requests>=2.0"]\n'
            ),
            encoding="utf-8",
        )

        rendered = TestsFlextInfraDepsModernizerMainExtra._ran_modernizer(
            modernizer_workspace
        )
        tm.that(rendered, has='"requests>=2.0"')
        tm.that(rendered, lacks='"requests>=2.32.4"')

    def test_run_scopes_default_audit_to_root_without_external_siblings(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Keep default modernization inside the declared workspace boundary."""
        workspace = u.Tests.mk_project(
            tmp_path,
            "flext",
            pyproject=(
                "[project]\n"
                "name='flext'\n"
                "version='0.1.0'\n"
                "requires-python='>=3.13,<3.14'\n"
                "dependencies=[]\n"
            ),
        )
        u.Tests.write_project_beads_config(workspace, "flext")
        external = tmp_path / "gruponos-data"
        (external / "src" / "gruponos_data").mkdir(parents=True)
        external_pyproject = external / c.PYPROJECT_FILENAME
        external_pyproject.write_text(
            "[project]\nname='gruponos-data'\ndependencies=['flext-core']\n",
            encoding="utf-8",
        )

        modernizer = FlextInfraPyprojectModernizer(
            repository_root=workspace, audit=True, skip_comments=True
        )

        tm.that(modernizer.run(), eq=1)
        output = capsys.readouterr().out
        tm.that(output, has="pyproject.toml:")
        tm.that(output, lacks=str(external_pyproject.resolve()))
        tm.that(output, lacks="not in the subpath")

    def test_conform_source_preserves_taplo_process_error(self, tmp_path: Path) -> None:
        """Return the exact formatter process failure from the public conform path."""
        (tmp_path / ".taplo.toml").write_text('include = ["/x/["]\n', encoding="utf-8")
        source = '[project]\nname = "sample"\nversion = "0.1.0"\n'
        modernizer = FlextInfraPyprojectModernizer(repository_root=tmp_path)

        result = modernizer.conform_source(source, path=tmp_path / "pyproject.toml")

        error = tm.fail(result)
        tm.that(error, has=["taplo format failed (1)", "invalid configuration", "/x/["])
        tm.that(
            error, lacks=["couldn't exec process", "pyproject tooling render failed"]
        )
