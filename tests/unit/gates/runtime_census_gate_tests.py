"""Runtime census selection and blocking behavior.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import importlib
import sys
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import m, t
from flext_infra.gates.runtime_census import FlextInfraRuntimeCensusGate
from flext_infra.validate.runtime_census import FlextInfraRuntimeCensusValidator

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


_MIXED_SOURCES: t.MappingKV[str, str] = {
    "pyproject.toml": '[project]\nname = "fixturecensusmixed"\nversion = "0.1.0"\n',
    "src/fixturecensusmixed/__init__.py": (
        '"""Fixture package tripping several census rule families."""\n'
        "\n"
        "from typing import ClassVar\n"
        "\n"
        "\n"
        "class Plain:\n"
        '    """Missing the project class prefix."""\n'
        "\n"
        "\n"
        "class Holder:\n"
        '    """Missing prefix plus a constant outside _constants."""\n'
        "\n"
        '    LABEL: ClassVar[str] = "x"\n'
    ),
}
_GENUINE_SOURCES: t.MappingKV[str, str] = {
    "pyproject.toml": ('[project]\nname = "fixturecensusgenuine"\nversion = "0.1.0"\n'),
    "src/fixturecensusgenuine/__init__.py": (
        '"""Fixture package whose only census violation is a genuine rule."""\n'
        "\n"
        "from typing import ClassVar\n"
        "\n"
        "\n"
        "class FixturecensusgenuineHolder:\n"
        '    """Correctly prefixed class with a constant outside _constants."""\n'
        "\n"
        '    LABEL: ClassVar[str] = "x"\n'
    ),
}


def _write_project(root: Path, sources: t.MappingKV[str, str]) -> Path:
    """Materialize one fixture project and return its repository root.

    Returns:
        The resulting ``Path``.

    """
    for relative, text in sources.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return root


@pytest.fixture
def mixed_project(tmp_path: Path) -> Iterator[Path]:
    """Importable project tripping several census rule families at once.

    Yields:
        Each ``Path``.

    """
    root = _write_project(tmp_path / "mixed", _MIXED_SOURCES)
    yield from _importable_project(root)


@pytest.fixture
def genuine_project(tmp_path: Path) -> Iterator[Path]:
    """Importable project tripping exactly one genuine census rule.

    Yields:
        Each ``Path``.

    """
    root = _write_project(tmp_path / "genuine", _GENUINE_SOURCES)
    yield from _importable_project(root)


def _importable_project(root: Path) -> Iterator[Path]:
    """Expose one fixture ``src`` tree to the import system for the census.

    Yields:
        Each ``Path``.

    """
    src = str(root / "src")
    sys.path.insert(0, src)
    importlib.invalidate_caches()
    try:
        yield root
    finally:
        sys.path.remove(src)
        importlib.invalidate_caches()


class TestRuntimeCensusSelection:
    """Empty discovery is a broken invocation, not evidence of conformance."""

    @staticmethod
    def test_empty_checkout_fails_the_gate(tmp_path: Path) -> None:
        """Test empty checkout fails the gate."""
        context = m.Infra.GateContext(
            repository_root=tmp_path,
            reports_dir=tmp_path / ".reports",
        )
        gate = FlextInfraRuntimeCensusGate(repository_root=tmp_path)
        result = gate.check(tmp_path, context).result
        tm.that(result.passed, eq=False)
        tm.that(" | ".join(result.errors), has="no projects")


class TestsRuntimeCensusBlocking:
    """Every census violation blocks; no rule family is set aside."""

    @staticmethod
    def test_every_rule_family_in_the_project_blocks(
        mixed_project: Path,
        genuine_project: Path,
    ) -> None:
        """Prefix and constant violations belong to runtime census.

        The parameter-count smell belongs to the smell owner (qlty through
        make smells, flext-core ea8d16d26), so the census never reports it:
        each finding has exactly one gate.
        """
        mixed = tm.ok(
            FlextInfraRuntimeCensusValidator(
                repository_root=mixed_project,
            ).build_report(),
        )
        genuine = tm.ok(
            FlextInfraRuntimeCensusValidator(
                repository_root=genuine_project,
            ).build_report(),
        )
        tm.that(mixed.passed, eq=False)
        tm.that("\n".join(mixed.violations), has="[ENFORCE-079]")
        tm.that("\n".join(mixed.violations), has="[class_prefix]")
        tm.that("\n".join(mixed.violations), lacks="[smell_function_parameters]")
        tm.that(len(mixed.violations) > len(genuine.violations), eq=True)
        tm.that(
            mixed.summary,
            eq=f"runtime census found {len(mixed.violations)} violation(s)",
        )
        context = m.Infra.GateContext(
            repository_root=mixed_project,
            reports_dir=mixed_project / ".reports",
        )
        gate = FlextInfraRuntimeCensusGate(repository_root=mixed_project)
        result = gate.check(mixed_project, context).result
        tm.that(result.passed, eq=False)
        tm.that("\n".join(result.errors), has="[ENFORCE-079]")
        tm.that("\n".join(result.errors), has="[class_prefix]")

    @staticmethod
    def test_single_violation_reports_verbatim(
        genuine_project: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """One genuine finding is one violation, reported exactly once."""
        report = tm.ok(
            FlextInfraRuntimeCensusValidator(
                repository_root=genuine_project,
            ).build_report(),
        )
        output = capsys.readouterr().out
        tm.that(report.passed, eq=False)
        tm.that(report.violations, length=1)
        tm.that("\n".join(report.violations), has="[ENFORCE-079]")
        tm.that(report.summary, eq="runtime census found 1 violation(s)")
        tm.that(output, eq="")
