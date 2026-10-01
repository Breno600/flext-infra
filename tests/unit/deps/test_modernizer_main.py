"""Public behavior tests for the pyproject modernizer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import FlextInfraPyprojectModernizer, main
from tests import c, m

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraDepsModernizerMain:
    """Validate only public modernizer behavior."""

    @staticmethod
    def test_initialization_uses_explicit_workspace(
        modernizer_workspace: Path,
    ) -> None:
        """Verify initialization uses explicit workspace."""
        modernizer = FlextInfraPyprojectModernizer(repository_root=modernizer_workspace)
        tm.that(modernizer.root, eq=modernizer_workspace)

    @staticmethod
    def test_conform_source_rejects_invalid_toml(
        modernizer_workspace: Path,
    ) -> None:
        """Invalid TOML fails closed with the offending path."""
        pyproject = modernizer_workspace / c.PYPROJECT_FILENAME
        tm.fail(
            FlextInfraPyprojectModernizer(
                repository_root=modernizer_workspace,
            ).conform_source(
                "invalid [[[",
                path=pyproject,
                topology=m.Infra.PyprojectDeclaredTopology(),
            ),
            has="invalid TOML",
        )

    @staticmethod
    def test_run_apply_updates_root_pyproject(modernizer_workspace: Path) -> None:
        """Verify run apply updates root pyproject."""
        modernizer = FlextInfraPyprojectModernizer(
            repository_root=modernizer_workspace,
            apply_changes=True,
            skip_comments=True,
            skip_check=True,
        )
        exit_code = modernizer.run()
        tm.that(exit_code, eq=0)
        tm.that(
            (modernizer_workspace / c.PYPROJECT_FILENAME).read_text(encoding="utf-8"),
            has='build-backend = "hatchling.build"',
        )

    @staticmethod
    def test_run_rejects_unknown_selected_project(
        modernizer_workspace: Path,
    ) -> None:
        """Verify run rejects unknown selected project."""
        modernizer = FlextInfraPyprojectModernizer(
            repository_root=modernizer_workspace,
            selected_projects=["missing-project"],
        )
        tm.that(modernizer.run(), eq=2)

    @staticmethod
    def test_cli_reports_pending_changes_in_audit_mode(
        modernizer_workspace: Path,
    ) -> None:
        """Verify cli reports pending changes in audit mode."""
        tm.that(
            main([
                "deps",
                "modernize",
                "--repository-root",
                str(modernizer_workspace),
                "--audit",
                "--skip-comments",
            ]),
            eq=1,
        )
