"""Behavior tests for the rope runtime module predicate.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra._utilities._rope.project import FlextInfraRopeProject
from flext_infra._utilities.rope_core import FlextInfraUtilitiesRopeCore
from flext_infra._utilities.rope_runtime import FlextInfraUtilitiesRopeRuntime

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraRopeRuntimePymodule:
    """Validate the module predicate over rope modules and packages."""

    @staticmethod
    def test_pymodule_contract_accepts_packages(tmp_path: Path) -> None:
        """A rope PyPackage satisfies the pymodule contract beside PyModule.

        ``find_module`` resolves an installed third-party package to its
        folder resource and ``get_pymodule`` returns a ``PyPackage`` for it;
        external base resolution (``pydantic.BaseModel`` and friends) reads
        attributes through packages, so the validated boundary must accept
        both shapes (fleet gen regression 2026-10-05).
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
        pymodule = FlextInfraUtilitiesRopeCore.resolve_pymodule(
            project,
            project.find_module("plain"),
        )
        pypackage = FlextInfraUtilitiesRopeCore.resolve_pymodule(
            project,
            project.find_module("pkg"),
        )
        assert FlextInfraUtilitiesRopeRuntime.pymodule(pymodule)
        assert FlextInfraUtilitiesRopeRuntime.pymodule(pypackage)
        assert pypackage.get_attribute("VALUE") is not None
