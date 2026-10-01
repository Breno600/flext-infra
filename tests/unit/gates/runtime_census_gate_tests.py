"""Runtime census selection and gate-suspension consistency behavior."""

from __future__ import annotations

import importlib
import sys
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import c, config, m, t
from flext_infra.gates.runtime_census import FlextInfraRuntimeCensusGate
from flext_infra.validate.runtime_census import FlextInfraRuntimeCensusValidator

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


_MIXED_SOURCES: t.MappingKV[str, str] = {
    "pyproject.toml": '[project]\nname = "fixturecensusmixed"\nversion = "0.1.0"\n',
    "src/fixturecensusmixed/__init__.py": (
        '"""Fixture package tripping suspended and genuine census families."""\n'
        "\n"
        "from typing import ClassVar\n"
        "\n"
        "\n"
        "class Plain:\n"
        '    """Missing the project class prefix."""\n'
        "\n"
        "    def run(self, a, b, c, d, e, f, g):\n"
        '        """Too many parameters for one function."""\n'
        "        return a + b + c + d + e + f + g\n"
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


def _owning_suspension(token: str) -> m.Infra.MakeGateSuspensionSpec | None:
    """Return the suspension whose census families cover ``token``, if any.

    Mirrors the census family contract the SSOT declares: ENFORCE-* families
    match one exact rule id, every other family matches the tag by prefix.
    """
    for suspension in config.Infra.codegen.make.check_gate_suspensions:
        for family in suspension.census_rule_families:
            if family.startswith("ENFORCE-"):
                covered = token == family
            else:
                covered = token.startswith(family)
            if covered:
                return suspension
    return None


def _write_project(root: Path, sources: t.MappingKV[str, str]) -> Path:
    """Materialize one fixture project and return its repository root."""
    for relative, text in sources.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return root


@pytest.fixture
def mixed_project(tmp_path: Path) -> Iterator[Path]:
    """Importable project tripping suspended and genuine families at once."""
    root = _write_project(tmp_path / "mixed", _MIXED_SOURCES)
    yield from _importable_project(root)


@pytest.fixture
def genuine_project(tmp_path: Path) -> Iterator[Path]:
    """Importable project tripping exactly one genuine census rule."""
    root = _write_project(tmp_path / "genuine", _GENUINE_SOURCES)
    yield from _importable_project(root)


def _importable_project(root: Path) -> Iterator[Path]:
    """Expose one fixture ``src`` tree to the import system for the census."""
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

    def test_empty_checkout_fails_the_gate(self, tmp_path: Path) -> None:
        context = m.Infra.GateContext(
            repository_root=tmp_path, reports_dir=tmp_path / ".reports"
        )
        gate = FlextInfraRuntimeCensusGate(repository_root=tmp_path)
        result = gate.check(tmp_path, context).result
        tm.that(result.passed, eq=False)
        tm.that(" | ".join(result.errors), has="no projects")


class TestsRuntimeCensusSuspensionConsistency:
    """The census honors recorded gate suspensions for the same families."""

    def test_suspended_families_leave_the_failure_count_under_loud_info(
        self, mixed_project: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Suspended tag families are suppressed with their recorded authority."""
        report = tm.ok(
            FlextInfraRuntimeCensusValidator(
                repository_root=mixed_project
            ).build_report()
        )
        output = capsys.readouterr().out
        for token in ("class_prefix",):
            owner = _owning_suspension(token)
            joined = "\n".join(report.violations)
            if owner is None:
                tm.that(joined, has=f"[{token}]")
                continue
            tm.that(joined, lacks=f"[{token}]")
            tm.that(output, has="SUSPENDED census rule family")
            tm.that(output, has=f"(gate {owner.gate})")
            tm.that(output, has=f"authority={owner.authority}")
        genuine_owner = _owning_suspension("ENFORCE-079")
        if genuine_owner is None:
            tm.that(report.passed, eq=False)
            tm.that("\n".join(report.violations), has="[ENFORCE-079]")
        else:
            tm.that(report.passed, eq=True)
        if _owning_suspension("class_prefix") is not None:
            tm.that(report.summary, has="suppressed under recorded gate suspensions")

    def test_genuine_rule_family_stays_fully_blocking(
        self, genuine_project: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """An unmapped rule keeps the census red with no suspension receipt."""
        report = tm.ok(
            FlextInfraRuntimeCensusValidator(
                repository_root=genuine_project
            ).build_report()
        )
        output = capsys.readouterr().out
        owner = _owning_suspension("ENFORCE-079")
        if owner is None:
            tm.that(report.passed, eq=False)
            tm.that("\n".join(report.violations), has="[ENFORCE-079]")
            tm.that(output, lacks="SUSPENDED census rule family")
            tm.that(report.summary, lacks="suppressed")
        else:
            tm.that(report.passed, eq=True)
            tm.that(output, has="SUSPENDED census rule family")
            tm.that(output, has=f"(gate {owner.gate})")

    def test_unmatched_project_reports_verbatim(
        self, genuine_project: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Without a matching suspension the report is the pre-contract census.

        The genuine fixture's findings stay verbatim: one violation, no
        suppression note, and no census suspension receipt on stdout.
        """
        report = tm.ok(
            FlextInfraRuntimeCensusValidator(
                repository_root=genuine_project
            ).build_report()
        )
        output = capsys.readouterr().out
        if _owning_suspension("ENFORCE-079") is None:
            tm.that(report.violations, length=1)
            tm.that(report.summary, eq="runtime census found 1 violation(s)")
            tm.that(output, eq="")


class TestsRuntimeCensusSmellOwnership:
    """Smell families belong to the smells gate, never to the check census."""

    @staticmethod
    def _smell_tokens(violations: t.SequenceOf[str]) -> tuple[str, ...]:
        """Violations whose trailing rule token is a flext-core smell tag."""
        return tuple(
            violation
            for violation in violations
            if any(violation.endswith(f"[{tag}]") for tag in c.ENFORCEMENT_SMELL_TAGS)
        )

    def test_check_census_never_sees_smell_families(
        self, mixed_project: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The runtime-census gate neither reports nor counts any smell.

        Premise (operator 2026-10-01): make smells owns every smell family;
        ownership is routing, so no smell is suspended, observational,
        suppressed, or announced inside make check.
        """
        report = tm.ok(
            FlextInfraRuntimeCensusValidator(
                repository_root=mixed_project
            ).build_report()
        )
        output = capsys.readouterr().out
        tm.that(self._smell_tokens(report.violations), length=0)
        for tag in c.ENFORCEMENT_SMELL_TAGS:
            tm.that(output, lacks=tag)
            tm.that(report.summary, lacks=tag)

    def test_smells_census_reports_only_smell_families(
        self, mixed_project: Path
    ) -> None:
        """The smells-scoped census grades exactly the smell families."""
        report = tm.ok(
            FlextInfraRuntimeCensusValidator(
                repository_root=mixed_project, census_gate=c.Infra.SMELLS
            ).build_report()
        )
        tm.that(report.passed, eq=False)
        tm.that(report.violations, length=len(self._smell_tokens(report.violations)))
        tm.that("\n".join(report.violations), has="[smell_function_parameters]")

    def test_gate_without_census_families_is_a_failure(
        self, mixed_project: Path
    ) -> None:
        """A gate that owns no census family cannot grade a census run."""
        tm.fail(
            FlextInfraRuntimeCensusValidator(
                repository_root=mixed_project, census_gate=c.Infra.LINT
            ).build_report(),
            has="has no rule families",
        )
