"""Real local installation preserves consumer resolution and isolation."""

from __future__ import annotations

import sys
import sysconfig
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, config
from tests import u


class TestsFlextInfraBindingInstall:
    """Exercise the public binding CLI with real consumer and supplier packages."""

    @pytest.mark.parametrize(
        "scenario", ["extras", "constraint", "inactive", "borrowed"]
    )
    def test_binding_uses_consumer_contract(
        self, tmp_path: Path, scenario: str
    ) -> None:
        """Install extras or reject incompatible, inactive, and borrowed candidates."""
        supplier, consumer, extra = (
            tmp_path / name for name in ("supplier", "consumer", "extra")
        )
        for root, name in (
            (supplier, "binding-candidate"),
            (consumer, "binding-consumer"),
        ):
            u.Tests.WorktreeFixture.initialize_governed_project(
                root, name, workspace=name, database=name, issue_prefix=name
            )
        extra.mkdir()
        for root, name, optional in (
            (extra, "binding-extra", ""),
            (
                supplier,
                "binding-candidate",
                f'\n[project.optional-dependencies]\nfeature = ["binding-extra @ {extra.as_uri()}"]\n',
            ),
        ):
            (root / c.PYPROJECT_FILENAME).write_text(
                '[build-system]\nrequires = ["setuptools"]\nbuild-backend = "setuptools.build_meta"\n'
                f'[project]\nname = "{name}"\nversion = "1.0.0"\n{optional}'
                f'\n[tool.setuptools]\npy-modules = ["{name.replace("-", "_")}"]\n',
                encoding=c.Cli.ENCODING_DEFAULT,
            )
            (root / f"{name.replace('-', '_')}.py").write_text(
                'VALUE = "installed"\n', encoding=c.Cli.ENCODING_DEFAULT
            )
        marker = "; python_version < '0'" if scenario == "inactive" else ""
        constraints = (
            '\n[tool.uv]\nconstraint-dependencies = ["binding-candidate>=2"]\n'
            if scenario == "constraint"
            else ""
        )
        declaration = consumer / c.PYPROJECT_FILENAME
        declaration.write_text(
            '[project]\nname = "binding-consumer"\nversion = "1.0.0"\n'
            f'dependencies = ["Binding_Candidate[feature]>=1{marker}"]\n{constraints}',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        original = declaration.read_bytes()
        tm.ok(u.Tests.create_python_environment(consumer))
        environment = u.Infra.runtime_environment_dir(consumer)
        if scenario == "borrowed":
            foreign = tmp_path / "foreign-environment"
            environment.rename(foreign)
            environment.symlink_to(foreign, target_is_directory=True)
        python = (
            Path(
                sysconfig.get_path(
                    "scripts",
                    scheme="venv",
                    vars={"base": str(environment), "platbase": str(environment)},
                )
            )
            / c.Infra.PromotedSelector.VENV_PYTHON
        )
        ci = config.Infra.codegen.make.ci
        outcome = tm.ok(
            u.Cli.run_raw(
                (
                    sys.executable,
                    "-m",
                    "flext_infra",
                    "workspace",
                    "flext-binding",
                    "--repository-root",
                    str(consumer),
                    "--flext-root",
                    str(supplier),
                    "--python",
                    str(python),
                ),
                env={ci.variable: ci.local_value},
            )
        )
        output = f"{outcome.stdout}{outcome.stderr}"
        tm.that(declaration.read_bytes(), eq=original)
        if scenario != "extras":
            tm.that(outcome.outcome.raw_return_code != 0, eq=True, msg=output)
            if scenario == "inactive":
                tm.that(output, has="no active declared dependency")
            elif scenario == "borrowed":
                tm.that(output, has="physical consumer environment")
            else:
                tm.that(output, has="binding-candidate")
            return
        tm.that(outcome.outcome.raw_return_code, eq=0, msg=output)
        installed = tm.ok(
            u.Cli.run((
                str(python),
                "-c",
                "import binding_candidate, binding_extra; print(binding_candidate.VALUE, binding_extra.VALUE)",
            ))
        )
        tm.that(installed.stdout.strip(), eq="installed installed")
