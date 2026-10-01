"""Public behavior tests for FlextInfraStubSupplyChain."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra.validate.stub_chain import FlextInfraStubSupplyChain

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraStubChain:
    """Declarative public-contract tests for stub-chain validation."""

    def test_project_names_and_dirs_are_normalized(self, tmp_path: Path) -> None:
        chain = FlextInfraStubSupplyChain(
            repository_root=tmp_path, selected_projects=[" alpha, beta ", "gamma delta"]
        )
        tm.that(chain.project_names, eq=["alpha", "beta", "gamma", "delta"])
        tm.that(
            chain.project_dirs,
            eq=[
                tmp_path / "alpha",
                tmp_path / "beta",
                tmp_path / "gamma",
                tmp_path / "delta",
            ],
        )

    def test_project_dirs_are_disabled_for_all_projects(self, tmp_path: Path) -> None:
        chain = FlextInfraStubSupplyChain(
            repository_root=tmp_path, selected_projects=["alpha"], all_projects=True
        )
        tm.that(chain.project_dirs is None, eq=True)

    def test_build_report_fails_for_missing_workspace(self, tmp_path: Path) -> None:
        result = FlextInfraStubSupplyChain(repository_root=tmp_path).build_report(
            tmp_path / "missing"
        )
        tm.fail(result, has="typed dependency workspace does not exist")
