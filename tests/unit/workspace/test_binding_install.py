"""Real local installation preserves consumer resolution and isolation.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import sys
import sysconfig
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, config
from tests import m, u


class TestsFlextInfraBindingInstall:
    """Exercise the public binding CLI with real consumer and supplier packages."""

    @staticmethod
    def _seed_candidate_projects(
        supplier: Path,
        consumer: Path,
        extra: Path,
        workspace: Path,
        *,
        scenario: str,
    ) -> None:
        """Initialize the governed consumer, supplier, and extra roots.

        The composed-member scenario makes the consumer a workspace member:
        its runtime environment is the workspace's, so its own environment
        path must not borrow it.
        """
        if scenario == "borrowed-member":
            u.Tests.WorktreeFixture.initialize_governed_project(
                workspace,
                "binding-workspace",
                beads=u.Tests.BeadsIdentity(
                    workspace="binding-workspace",
                    database="binding-workspace",
                    issue_prefix="binding-workspace",
                ),
            )
            consumer = workspace / consumer.name
        for root, name in (
            (supplier, "binding-candidate"),
            (consumer, "binding-consumer"),
        ):
            u.Tests.WorktreeFixture.initialize_governed_project(
                root,
                name,
                beads=u.Tests.BeadsIdentity(
                    workspace=name,
                    database=name,
                    issue_prefix=name,
                ),
            )
        extra.mkdir()
        for root, name, optional in (
            (extra, "binding-extra", ""),
            (
                supplier,
                "binding-candidate",
                (
                    "\n[project.optional-dependencies]\n"
                    f'feature = ["binding-extra @ {extra.as_uri()}"]\n'
                ),
            ),
        ):
            (root / c.PYPROJECT_FILENAME).write_text(
                '[build-system]\nrequires = ["setuptools"]\n'
                'build-backend = "setuptools.build_meta"\n'
                f'[project]\nname = "{name}"\nversion = "1.0.0"\n{optional}'
                f'\n[tool.setuptools]\npy-modules = ["{name.replace("-", "_")}"]\n',
                encoding=c.Cli.ENCODING_DEFAULT,
            )
            (root / f"{name.replace('-', '_')}.py").write_text(
                'VALUE = "installed"\n',
                encoding=c.Cli.ENCODING_DEFAULT,
            )

    @staticmethod
    def _declare_consumer_dependency(scenario: str, consumer: Path) -> bytes:
        """Write the consumer's declared dependency contract for one scenario.

        Returns:
            The declaration bytes the binding run must leave untouched.

        """
        inactive = "; python_version < '0'"
        marker = inactive if scenario == "inactive" else ""
        policy = []
        if scenario in {"override", "override-constraint"}:
            policy.append('override-dependencies = ["binding-candidate==1"]')
        if scenario == "inactive-override":
            policy.append(f'override-dependencies = ["binding-candidate==1{inactive}"]')
        if scenario in {"constraint", "override-constraint"}:
            policy.append('constraint-dependencies = ["binding-candidate>=2"]')
        constraints = "\n[tool.uv]\n" + "\n".join(policy) if policy else ""
        minimum = (
            "2"
            if scenario in {"override", "override-constraint", "inactive-override"}
            else "1"
        )
        declaration = consumer / c.PYPROJECT_FILENAME
        declaration.write_text(
            '[project]\nname = "binding-consumer"\nversion = "1.0.0"\n'
            f'dependencies = ["Binding_Candidate[feature]>={minimum}{marker}"]\n'
            f"{constraints}",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        return declaration.read_bytes()

    @staticmethod
    def _compose_consumer_environment(
        tmp_path: Path,
        consumer: Path,
        workspace: Path,
        *,
        scenario: str,
    ) -> Path:
        """Materialize the consumer runtime environment for one scenario.

        The composed member borrows the workspace environment through its own
        symlink; the borrowed scenario swaps the physical directory for a
        foreign symlinked environment.

        Returns:
            The consumer's resolved runtime environment directory.

        """
        if scenario == "borrowed-member":
            u.Tests.WorktreeFixture.attach_submodule(
                workspace,
                consumer,
                distribution="binding-consumer",
                relative_path=consumer.name,
            )
            tm.ok(u.Tests.create_python_environment(workspace))
            (consumer / c.Infra.ENVIRONMENT_DIRECTORY).symlink_to(
                u.Infra.runtime_environment_dir(consumer),
                target_is_directory=True,
            )
        else:
            tm.ok(u.Tests.create_python_environment(consumer))
        environment = u.Infra.runtime_environment_dir(consumer)
        if scenario == "borrowed":
            foreign = tmp_path / "foreign-environment"
            environment.rename(foreign)
            environment.symlink_to(foreign, target_is_directory=True)
        return environment

    @staticmethod
    @pytest.mark.slow
    @pytest.mark.parametrize(
        "scenario",
        [
            "extras",
            "constraint",
            "inactive",
            "borrowed",
            "borrowed-member",
            "override",
            "override-constraint",
            "inactive-override",
        ],
    )
    def test_binding_uses_consumer_contract(
        tmp_path: Path,
        scenario: str,
    ) -> None:
        """Install extras or reject incompatible, inactive, and borrowed candidates."""
        supplier, consumer, extra, workspace = (
            tmp_path / name for name in ("supplier", "consumer", "extra", "workspace")
        )
        TestsFlextInfraBindingInstall._seed_candidate_projects(
            supplier,
            consumer,
            extra,
            workspace,
            scenario=scenario,
        )
        declaration = consumer / c.PYPROJECT_FILENAME
        original = TestsFlextInfraBindingInstall._declare_consumer_dependency(
            scenario,
            consumer,
        )
        environment = TestsFlextInfraBindingInstall._compose_consumer_environment(
            tmp_path,
            consumer,
            workspace,
            scenario=scenario,
        )
        python = (
            Path(
                sysconfig.get_path(
                    "scripts",
                    scheme="venv",
                    vars={"base": str(environment), "platbase": str(environment)},
                ),
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
                options=m.Cli.ProcessOptions(env={ci.variable: ci.local_value}),
            ),
        )
        output = f"{outcome.stdout}{outcome.stderr}"
        tm.that(declaration.read_bytes(), eq=original)
        if scenario not in {"extras", "override"}:
            tm.that(outcome.outcome.raw_return_code != 0, eq=True, msg=output)
            if scenario == "inactive":
                tm.that(output, has="no active declared dependency")
            elif scenario in {"borrowed", "borrowed-member"}:
                tm.that(output, has="physical consumer environment")
            else:
                tm.that(output, has="binding-candidate")
            return
        tm.that(u.Cli.process_succeeded(outcome.outcome), eq=True, msg=output)
        installed = tm.ok(
            u.Cli.run((
                str(python),
                "-c",
                (
                    "import binding_candidate, binding_extra; "
                    "print(binding_candidate.VALUE, binding_extra.VALUE)"
                ),
            )),
        )
        tm.that(installed.stdout.strip(), eq="installed installed")
