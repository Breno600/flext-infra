"""CLI contract tests for the centralized validate CLI group."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import main as infra_main
from tests import u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraValidateCli:
    """Exercise the public validate CLI entrypoints."""

    def test_stub_validate_accepts_all_flag(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)

        tm.that(
            infra_main([
                "validate",
                "stub-validate",
                "--repository-root",
                str(workspace),
                "--all",
            ]),
            eq=0,
        )

    def test_stub_validate_help_returns_zero(self) -> None:
        tm.that(infra_main(["validate", "stub-validate", "--help"]), eq=0)

    def test_namespace_validate_runs_with_facade_composed_rope(
        self,
        tmp_path: Path,
    ) -> None:
        project = u.Tests.namespace_project(
            tmp_path,
            module_source=u.Tests.namespace_fixture("rule0_valid.py"),
            module_name="models.py",
        )

        exit_code = infra_main([
            "validate",
            "namespace",
            "--repository-root",
            str(project),
        ])

        tm.that(exit_code, eq=0)

    def test_namespace_validate_exits_nonzero_for_real_violations(
        self,
        tmp_path: Path,
    ) -> None:
        project = u.Tests.namespace_project(
            tmp_path,
            module_source=u.Tests.namespace_fixture("rule0_no_class.py"),
            module_name="models.py",
        )

        exit_code = infra_main([
            "validate",
            "namespace",
            "--repository-root",
            str(project),
        ])

        tm.that(exit_code, eq=1)
