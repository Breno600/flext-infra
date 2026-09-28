"""Verify ci.yml installs the runner packages a distribution declares."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import c, u
from tests import t

from ._support import CodegenTestSupport


class TestsFlextInfraCiSystemPackages:
    """A declared engine is installed on the runner; nothing is skipped."""

    ci_template = (
        Path(__file__).resolve().parents[3]
        / "src/flext_infra/templates/project/base/.github/workflows/ci.yml.j2"
    )
    step_name = "Install declared system packages"

    @classmethod
    def _render_ci(cls, *, system_packages: t.VariadicTuple[str]) -> str:
        spec = CodegenTestSupport.Ci.workflow_spec(
            dist="fixture-engine",
            make_profile=c.Infra.MakeProfile.STANDALONE,
            repository_branch="develop",
            ci_trigger_branches=("develop", "main"),
            system_packages=system_packages,
        )
        return tm.ok(u.Cli.template_render(cls.ci_template, spec))

    def test_declared_packages_render_one_install_step_before_the_gates(self) -> None:
        rendered = self._render_ci(system_packages=("engine-calc", "engine-fonts"))

        tm.that(rendered.count(self.step_name), eq=1)
        tm.that(
            rendered,
            has="apt-get install -y -qq --no-install-recommends engine-calc engine-fonts",
        )
        tm.that(
            rendered.index(self.step_name) < rendered.index("setup (blocking)"), eq=True
        )

    def test_no_declaration_renders_no_install_step(self) -> None:
        rendered = self._render_ci(system_packages=())

        tm.that(rendered, lacks=self.step_name)
