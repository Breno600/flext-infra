"""Behavior tests for the rope runtime module predicate.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import FlextInfraRopeWorkspace, c, t, u
from flext_infra._utilities import (
    FlextInfraRopeProject,
    FlextInfraUtilitiesRopeCore,
    FlextInfraUtilitiesRopeRuntime,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraRopeRuntimePymodule:
    """Validate the module predicate over rope modules and packages."""

    @staticmethod
    @pytest.mark.parametrize("regular_package", [False, True])
    def test_module_precedes_namespace_but_not_regular_package(
        tmp_path: Path,
        *,
        regular_package: bool,
    ) -> None:
        """Python source wins over a data directory, not an initialized package.

        Raises:
            AssertionError: If Native Rope finder did not resolve the fixture module.
        """
        root = tmp_path / "consumer"
        source = root / "src"
        source.mkdir(parents=True)
        (source / "contract.py").write_text(
            "class ModuleContract:\n    pass\n",
            encoding=c.Infra.ENCODING_DEFAULT,
        )
        package = source / "contract"
        package.mkdir()
        if regular_package:
            (package / c.Infra.INIT_PY).write_text(
                "class PackageContract:\n    pass\n",
                encoding=c.Infra.ENCODING_DEFAULT,
            )
        with FlextInfraRopeWorkspace.open_workspace(root) as workspace:
            resource = workspace.rope_project.find_module("contract")
            tm.that(resource, none=False)
            if resource is None:
                message = "Native Rope finder did not resolve the fixture module"
                raise AssertionError(message)
            module = u.Infra.resolve_pymodule(workspace.rope_project, resource)
            expected = "PackageContract" if regular_package else "ModuleContract"
            tm.that(module.get_attribute(expected).get_object().get_name(), eq=expected)

    @staticmethod
    def test_pymodule_contract_accepts_packages(tmp_path: Path) -> None:
        """A rope PyPackage satisfies the pymodule contract beside PyModule.

        ``find_module`` resolves an installed third-party package to its
        folder resource and ``get_pymodule`` returns a ``PyPackage`` for it;
        external base resolution (``pydantic.BaseModel`` and friends) reads
        attributes through packages, so the validated boundary must accept
        both shapes (fleet gen regression 2026-10-05).

        Raises:
            ValueError: If fixture modules are missing from the snapshot project.

        """
        package_root = tmp_path / "pkg"
        package_root.mkdir()
        init_module = package_root / "__init__.py"
        init_module.write_text("VALUE = 1\n")
        plain_module = tmp_path / "plain.py"
        plain_module.write_text("VALUE = 2\n")
        sources = {
            init_module: init_module.read_text(),
            plain_module: plain_module.read_text(),
        }
        project = FlextInfraRopeProject.from_snapshot(
            str(tmp_path),
            sources,
            source_folders=["."],
        )
        rope_project: t.Infra.RopeProject = project
        plain_resource = project.find_module("plain")
        pkg_resource = project.find_module("pkg")
        if plain_resource is None or pkg_resource is None:
            msg = "fixture modules missing from the snapshot project"
            raise ValueError(msg)
        pymodule = FlextInfraUtilitiesRopeCore.resolve_pymodule(
            rope_project,
            plain_resource,
        )
        pypackage = FlextInfraUtilitiesRopeCore.resolve_pymodule(
            rope_project,
            pkg_resource,
        )
        assert FlextInfraUtilitiesRopeRuntime.pymodule(pymodule)
        assert FlextInfraUtilitiesRopeRuntime.pymodule(pypackage)
        assert pypackage.get_attribute("VALUE") is not None
