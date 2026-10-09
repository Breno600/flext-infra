"""Unit tests for the canonical import-form normalization engine.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra.refactor import FlextInfraImportNormalization
from tests import u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraRefactorImportNormalization:
    """Behavior contract for test_infra_refactor_import_normalization."""

    @staticmethod
    def test_import_normalization_merges_alias_split_letters(
        tmp_path: Path,
    ) -> None:
        """The alias-split letter forms collapse into one root-combined line."""
        project = tmp_path / "project"
        package = u.Tests.src_package(
            project,
            "demo_pkg",
            pyproject="[project]\nname='demo'\n",
        )
        source = (
            "from __future__ import annotations\n"
            "\n"
            "from demo_pkg import constants as c\n"
            "from demo_pkg import models as m\n"
            "from demo_pkg import typings as t\n"
            "\n"
            "\n"
            "def run() -> str:\n"
            "    return f'{c}:{m}:{t}'\n"
        )

        normalized = FlextInfraImportNormalization.normalize_source(
            project_root=project,
            file_path=package / "service.py",
            source=source,
        )

        tm.that(normalized is not None, eq=True)
        tm.that(normalized, has="from demo_pkg import c, m, t")
        tm.that(normalized, lacks="constants as")
        tm.that(normalized, lacks="models as")
        tm.that(normalized, lacks="typings as")

    @staticmethod
    def test_import_normalization_flattens_facade_file_letters(
        tmp_path: Path,
    ) -> None:
        """The facade-file letter form rebinds through the package root."""
        project = tmp_path / "project"
        package = u.Tests.src_package(
            project,
            "demo_pkg",
            pyproject="[project]\nname='demo'\n",
        )
        source = (
            "from __future__ import annotations\n"
            "\n"
            "from demo_pkg.typings import t\n"
            "\n"
            "\n"
            "def run(value: t.StrSequence) -> str:\n"
            "    return ','.join(value)\n"
        )

        normalized = FlextInfraImportNormalization.normalize_source(
            project_root=project,
            file_path=package / "service.py",
            source=source,
        )

        tm.that(normalized is not None, eq=True)
        tm.that(normalized, has="from demo_pkg import t")
        tm.that(normalized, lacks="from demo_pkg.typings import")

    @staticmethod
    def test_import_normalization_rewrites_relative_own_package_imports(
        tmp_path: Path,
    ) -> None:
        """A relative own-package letter import becomes the root-combined form."""
        project = tmp_path / "project"
        package = u.Tests.src_package(
            project,
            "demo_pkg",
            pyproject="[project]\nname='demo'\n",
        )
        nested = package / "_utilities"
        nested.mkdir()
        (nested / "__init__.py").write_text("", encoding="utf-8")
        source = (
            "from __future__ import annotations\n"
            "\n"
            "from ..typings import t\n"
            "\n"
            "\n"
            "def run(value: t.StrSequence) -> str:\n"
            "    return ','.join(value)\n"
        )

        normalized = FlextInfraImportNormalization.normalize_source(
            project_root=project,
            file_path=nested / "helper.py",
            source=source,
        )

        tm.that(normalized is not None, eq=True)
        tm.that(normalized, has="from demo_pkg import t")
        tm.that(normalized, lacks="from ..typings import")

    @staticmethod
    def test_import_normalization_removes_import_guards(
        tmp_path: Path,
    ) -> None:
        """A guarded import becomes a clean module-level binding."""
        project = tmp_path / "project"
        package = u.Tests.src_package(
            project,
            "demo_pkg",
            pyproject="[project]\nname='demo'\n",
        )
        source = (
            "from __future__ import annotations\n"
            "\n"
            "try:\n"
            "    from demo_pkg import u\n"
            "except ImportError:  # pragma: no cover\n"
            "    u = None  # type: ignore[assignment]\n"
            "\n"
            "\n"
            "def run() -> object:\n"
            "    return u\n"
        )

        normalized = FlextInfraImportNormalization.normalize_source(
            project_root=project,
            file_path=package / "service.py",
            source=source,
        )

        tm.that(normalized is not None, eq=True)
        tm.that(normalized, lacks="except ImportError")
        tm.that(normalized, lacks="= None  # type: ignore")
        tm.that(normalized, has="from demo_pkg import u")

    @staticmethod
    def test_import_normalization_is_idempotent(
        tmp_path: Path,
    ) -> None:
        """A second pass over the normalized source changes nothing."""
        project = tmp_path / "project"
        package = u.Tests.src_package(
            project,
            "demo_pkg",
            pyproject="[project]\nname='demo'\n",
        )
        source = (
            "from __future__ import annotations\n"
            "\n"
            "from demo_pkg import constants as c\n"
            "from demo_pkg.typings import t\n"
            "\n"
            "\n"
            "def run(value: t.StrSequence) -> str:\n"
            "    return f'{c}:{value}'\n"
        )

        first = FlextInfraImportNormalization.normalize_source(
            project_root=project,
            file_path=package / "service.py",
            source=source,
        )
        tm.that(first is not None, eq=True)
        normalized = first or ""
        second = FlextInfraImportNormalization.normalize_source(
            project_root=project,
            file_path=package / "service.py",
            source=normalized,
        )

        tm.that(second, eq=None)
